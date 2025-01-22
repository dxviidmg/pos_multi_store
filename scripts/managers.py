from products.models import Store, Product, Brand, StoreProduct
import xlrd
from decimal import Decimal
from tqdm import tqdm
from decimal import Decimal
from tenants.models import Tenant
from clients.models import Discount, Client


class TenantManager:
    """Clase para gestionar la creación de tiendas y usuarios."""

    def __init__(self, data_tenant):
        self.data_tenant = data_tenant

    def create_tenant(self):
        tenant, created = Tenant.objects.get_or_create(**self.data_tenant)
        return tenant


class StoreManager:
    """Clase para gestionar la creación de tiendas y usuarios."""

    def __init__(self, tenant):
        self.tenant = tenant

    def create_store(self, data):
        Store.objects.get_or_create(**data, tenant=self.tenant)

    def create_stores(self, stores_data):
        for data in stores_data:
            self.create_store(data)


class ProductManager:
    def __init__(self, tenant):
        self.tenant = tenant

    def clean_price(self, value):
        return Decimal(value.replace("$", "").replace(",", ""))

    def create_product_from_eleventa(self, row_values):
        code = str(row_values[0])
        name = (
            row_values[1]
            .lower()
            .strip()
        )

        purchase_price = self.clean_price(row_values[2])
        unit_sale_price = self.clean_price(row_values[3])
        wholesale_sale_price = (
            self.clean_price(row_values[4]) if row_values[4] else None
        )
        wholesale_sale_price = (
            wholesale_sale_price if unit_sale_price != wholesale_sale_price else None
        )
        min_wholesale_quantity = 3 if wholesale_sale_price else None

        # Procesar marca
        brand_name = (
            row_values[8]
            .replace(".", "")
            .replace(",", "")
            .replace("- Sin Departamento -", "NA")
            .strip()
            .title()
        )
        if len(brand_name) <= 2:
            brand_name = brand_name.upper()
        name = name.strip().capitalize()
        # Crear objetos relacionados
        brand, _ = Brand.objects.get_or_create(name=brand_name, tenant=self.tenant)

        # Datos del producto
        product_data = {
            "code": code,
            "name": name,
            "purchase_price": purchase_price,
            "unit_sale_price": unit_sale_price,
            "wholesale_sale_price": wholesale_sale_price,
            "min_wholesale_quantity": min_wholesale_quantity,
        }

        # Crear el producto
        Product.objects.get_or_create(
            code=code, defaults={**product_data, "brand": brand}
        )

    def read_file_from_eleventa(self, file_path):
        workbook = xlrd.open_workbook(file_path)
        return workbook.sheet_by_index(0)

    def create_products_from_eleventa(self, file_path):
        file = self.read_file_from_eleventa(file_path)
        for row_idx in tqdm(
            range(1, file.nrows), desc="Creating Products", unit="product"
        ):
            row_values = file.row_values(row_idx)
            self.create_product_from_eleventa(row_values)

    def create_demo_product(self, demo_product):
        # Procesar marca
        code = demo_product.pop("code")
        brand_name = demo_product.pop("brand")
        # Crear objetos relacionados
        brand, _ = Brand.objects.get_or_create(name=brand_name, tenant=self.tenant)
        # Crear el producto
        product, _ = Product.objects.get_or_create(
            code=code, defaults={**demo_product, "brand": brand}
        )

        StoreProduct.objects.filter(product=product).update(stock=10)

    def create_demo_products(self, demo_products):
        for demo_product in tqdm(
            demo_products, desc="Creating Products", unit="product"
        ):
            self.create_demo_product(demo_product)


class ClientManager:
    def __init__(self, tenant):
        self.tenant = tenant

    def create_demo_client(self, demo_client):
        # Procesar marca
        discount = demo_client.pop("discount_percentage")
        discount, _ = Discount.objects.get_or_create(
            discount_percentage=discount, tenant=self.tenant
        )
        # Crear el producto
        client, _ = Client.objects.get_or_create(
            defaults={**demo_client, "discount": discount}
        )

    def create_demo_clients(self, demo_clients):
        for demo_client in tqdm(demo_clients, desc="Creating Products", unit="product"):
            self.create_demo_client(demo_client)
