import io
import json

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from logs.models import StoreProductLog
from tenants.models import Tenant

from .models import Brand, Department, Product, Store, StoreProduct

COLUMNS = [
    "Código", "Marca", "Departamento", "Nombre", "Costo", "Precio unitario", "Precio mayoreo",
    "Cantidad minima mayoreo", "Precio Mayoreo en descuento de clientes", "Unidad", "Inventario",
]
ELEVENTA_HEADER = "Codigo\tDescripcion\tPrecio Costo\tPrecio Venta\tPrecio Mayoreo\tInventario\tInv. Minimo\tDepartamento"


def template_file(*records):
    buffer = io.BytesIO()
    pd.DataFrame(list(records), columns=COLUMNS).to_excel(buffer, index=False)
    return SimpleUploadedFile("p.xlsx", buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def record(code="A", brand="M", department="D", name="N", cost=1, unit_price=2, quantity=3, **extra):
    base = [code, brand, department, name, cost, unit_price, None, None, None, None, quantity]
    return base


class ImportViewsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="t1", short_name="t1")
        self.store = Store.objects.create(tenant=self.tenant, name="s1", store_type="T")
        self.client = APIClient()
        self.client.force_authenticate(user=self.tenant.owner)
        self.options = {"create_brands": "Y", "create_departments": "Y", "departments_mandatory": "N", "import_stock": "Y"}

    def post(self, url, file, **data):
        return self.client.post(url, {"file": file, **self.options, **data}, format="multipart")

    def test_traditional_validation_edits_and_import(self):
        file = template_file(record(code="A", cost=0), record(code="B"), record(code="C", cost=5))
        response = self.post("/api/products/import-validation/", file)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([r["status"] for r in response.json()],
                         ["Costo y precio(s) deben ser mayores a 0", "Exitoso", "Costo debe ser menor que precio unitario"])

        edits = json.dumps({"2": {"cost": "1.5"}})
        response = self.post("/api/products/import-validation/", template_file(record(code="A", cost=0), record(code="B"), record(code="C", cost=5)),
                             edits=edits, removed_rows=json.dumps([4]))
        self.assertEqual([r["status"] for r in response.json()], ["Exitoso", "Exitoso"])

        bad = self.post("/api/products/import/", template_file(record(code="A", cost=0)))
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(Product.objects.count(), 0)

        ok = self.post("/api/products/import/", template_file(record(code="A", cost=0), record(code="B", quantity=0), record(code="C", cost=5)),
                       edits=edits, removed_rows=json.dumps([4]), excluded_codes=json.dumps(["B"]))
        self.assertEqual(ok.status_code, 200, ok.content)
        product = Product.objects.get()
        self.assertEqual((product.code, float(product.cost), product.brand.name, product.department.name), ("A", 1.5, "M", "D"))
        self.assertEqual(float(StoreProduct.objects.get(product=product).stock), 3)
        self.assertEqual(StoreProductLog.objects.count(), 1)

    def test_traditional_existing_code_and_missing_brand_option(self):
        brand = Brand.objects.create(name="M", tenant=self.tenant)
        Product.objects.create(brand=brand, code="A", name="x", cost=1, unit_price=2)
        response = self.post("/api/products/import-validation/", template_file(record(code="A"), record(code="Z", brand="Otra")),
                             create_brands="N", create_departments="N", departments_mandatory="Y")
        self.assertEqual([r["status"] for r in response.json()], ["Código existente en el sistema", "Departamento inexistente"])
        Department.objects.create(name="D", tenant=self.tenant)
        response = self.post("/api/products/import-validation/", template_file(record(code="Z", brand="Otra", department="D")),
                             create_brands="N", create_departments="N", departments_mandatory="Y")
        self.assertEqual(response.json()[0]["status"], "Marca inexistente")

    def test_eleventa_validation_and_import_with_edits(self):
        def eleventa_file():
            text = "\r\n".join([ELEVENTA_HEADER, "A\tUno\t$0.00\t$2.00\t$0.00\t5\t0\t- Sin Departamento -", "B\tDos\t$1.00\t$2.00\t$0.00\t0\t0\tX"])
            return SimpleUploadedFile("e.xls", text.encode("cp1252"), content_type="application/vnd.ms-excel")
        data = {"brand": "Sin marca", "wholesale_mode": "ignore", "import_stock": "Y"}
        response = self.client.post("/api/products/eleventa/import-validation/", {"file": eleventa_file(), **data}, format="multipart")
        self.assertEqual([r["status"] for r in response.json()], ["Costo debe ser mayor a 0", "Exitoso"])
        response = self.client.post("/api/products/eleventa/import/", {"file": eleventa_file(), **data,
                                    "edits": json.dumps({"2": {"cost": "1"}}), "excluded_codes": json.dumps(["B"])}, format="multipart")
        self.assertEqual(response.status_code, 200, response.content)
        product = Product.objects.get()
        self.assertEqual((product.code, product.department), ("A", None))
        self.assertEqual(float(StoreProduct.objects.get(product=product).stock), 5)
