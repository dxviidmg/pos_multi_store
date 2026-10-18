import io
import unittest

import pandas as pd

from .import_corrections import SUCCESS_STATUS
from .product_import import (
    apply_template_edits,
    parse_template_edits,
    read_template_rows,
    validate_product_rows,
)

COLUMNS = [
    "Código", "Marca", "Departamento", "Nombre", "Costo", "Precio unitario", "Precio mayoreo",
    "Cantidad minima mayoreo", "Precio Mayoreo en descuento de clientes", "Unidad", "Inventario",
]
OPTIONS = {"create_brands": "Y", "create_departments": "Y", "departments_mandatory": "N", "import_stock": "N"}
LOOKUPS = {"existing_codes": set(), "brands": set(), "departments": set()}


def make_rows(*records, import_stock="Y"):
    buffer = io.BytesIO()
    pd.DataFrame(list(records), columns=COLUMNS).to_excel(buffer, index=False)
    buffer.seek(0)
    return read_template_rows(buffer, import_stock)


def row(code="A", brand="M", department=None, name="N", cost=1, unit_price=2, wholesale=None,
        min_quantity=None, discount=None, unit=None, quantity=1):
    return [code, brand, department, name, cost, unit_price, wholesale, min_quantity, discount, unit, quantity]


def statuses(*records, lookups=LOOKUPS, **options):
    rows = make_rows(*records)
    return [r["status"] for r in validate_product_rows(rows, lookups, {**OPTIONS, **options})]


class ReadTemplateRowsTests(unittest.TestCase):
    def test_reads_and_normalizes(self):
        rows = make_rows(row(code=123.0, brand=" M ", department="D", discount=1, unit="kg", wholesale=1.5, min_quantity=3))
        self.assertEqual(rows[0]["excel_row"], 2)
        self.assertEqual(rows[0]["code"], "123")
        self.assertEqual(rows[0]["brand"], "M")
        self.assertEqual(rows[0]["department"], "D")
        self.assertEqual(rows[0]["unit"], "KG")
        self.assertTrue(rows[0]["wholesale_price_on_client_discount"])
        self.assertEqual((rows[0]["wholesale_price"], rows[0]["min_wholesale_quantity"]), (1.5, 3.0))

    def test_wrong_columns(self):
        buffer = io.BytesIO()
        pd.DataFrame([[1, 2]], columns=["a", "b"]).to_excel(buffer, index=False)
        buffer.seek(0)
        with self.assertRaisesRegex(ValueError, "Formato de excel incorrecto"):
            read_template_rows(buffer, "N")


class ValidateProductRowsTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(statuses(row()), [SUCCESS_STATUS])

    def test_code_and_brand(self):
        self.assertEqual(statuses(row(code=None)), ["Sin código"])
        self.assertEqual(statuses(row(brand=None)), ["Sin marca"])

    def test_existing_and_duplicated_codes(self):
        lookups = {**LOOKUPS, "existing_codes": {"A"}}
        self.assertEqual(statuses(row(), lookups=lookups), ["Código existente en el sistema"])
        self.assertEqual(statuses(row(), row(name="O")), [SUCCESS_STATUS, "Código existente en la fila 2"])

    def test_row_without_brand_does_not_register_its_code(self):
        self.assertEqual(statuses(row(brand=None), row()), ["Sin marca", SUCCESS_STATUS])

    def test_prices(self):
        self.assertEqual(statuses(row(cost=0)), ["Costo y precio(s) deben ser mayores a 0"])
        self.assertEqual(statuses(row(cost=None)), ["Costo y precio(s) deben ser mayores a 0"])
        self.assertEqual(statuses(row(cost=5, unit_price=2)), ["Costo debe ser menor que precio unitario"])
        self.assertEqual(statuses(row(cost="abc")), ["Precios o costos inválidos"])

    def test_wholesale(self):
        self.assertEqual(statuses(row(wholesale=1.5)), ["Si existe mayoreo debe ingresar el precio mayoreo y la cantidad mínima"])
        self.assertEqual(statuses(row(wholesale=1.5, min_quantity=3)), [SUCCESS_STATUS])
        self.assertEqual(statuses(row(wholesale=3, min_quantity=3)), ["Precio mayoreo es mas grande que precio unitario"])
        self.assertEqual(statuses(row(cost=1.5, unit_price=4, wholesale=1, min_quantity=3)), ["Precio mayoreo es mas chico que costo"])
        self.assertEqual(statuses(row(wholesale=1.5, min_quantity=1)), ["Cantidad minima mayoreo debe ser entero minimo 2"])
        self.assertEqual(statuses(row(wholesale=1.5, min_quantity="x")), ["Cantidad minima mayoreo debe ser un numero entero"])

    def test_brand_and_department_lookups(self):
        self.assertEqual(statuses(row(), create_brands="N"), ["Marca inexistente"])
        lookups = {**LOOKUPS, "brands": {"M"}}
        self.assertEqual(statuses(row(), lookups=lookups, create_brands="N"), [SUCCESS_STATUS])
        self.assertEqual(
            statuses(row(department="D"), create_departments="N", departments_mandatory="Y"), ["Departamento inexistente"]
        )
        self.assertEqual(statuses(row(department="D"), create_departments="N", departments_mandatory="N"), [SUCCESS_STATUS])

    def test_stock_and_unit(self):
        self.assertEqual(statuses(row(quantity=-1), import_stock="Y"), ["Inventario debe ser un número positivo"])
        self.assertEqual(statuses(row(quantity=-1), import_stock="N"), [SUCCESS_STATUS])
        self.assertIn("Unidad inválida", statuses(row(unit="XX"))[0])
        self.assertEqual(
            statuses(row(unit="KG", wholesale=1.5, min_quantity=3)), ["Productos a granel no pueden tener precio de mayoreo"]
        )


class EditsTests(unittest.TestCase):
    def test_edit_fixes_row_and_removed_rows_are_dropped(self):
        rows = make_rows(row(cost=0), row(code="B"))
        edits = parse_template_edits('{"2": {"cost": "1.5", "brand": " X ", "unit": "lt", "wholesale_price_on_client_discount": "true"}}')
        fixed = apply_template_edits(rows, edits, {3})
        self.assertEqual(len(fixed), 1)
        self.assertEqual((fixed[0]["cost"], fixed[0]["brand"], fixed[0]["unit"]), (1.5, "X", "LT"))
        self.assertTrue(fixed[0]["wholesale_price_on_client_discount"])
        self.assertEqual([r["status"] for r in validate_product_rows(fixed, LOOKUPS, OPTIONS)], [SUCCESS_STATUS])

    def test_department_can_be_cleared(self):
        rows = make_rows(row(department="D"))
        self.assertIsNone(apply_template_edits(rows, {2: {"department": ""}}, set())[0]["department"])

    def test_unknown_field_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_template_edits('{"2": {"image": "a"}}')
