from products.models import Store, Product, Brand, StoreProduct
from django.contrib.auth.models import User
import xlrd
from decimal import Decimal
from tqdm import tqdm 
from django.contrib.auth.hashers import make_password
from decimal import Decimal
from tenants.models import Tenant


class TenantManager:
    """Clase para gestionar la creación de tiendas y usuarios."""

    def __init__(self, name):
        self.name = name


    def create_tenant(self):
        data = {
            'name': self.name
        }

        tenant, created = Tenant.objects.get_or_create(**data)
        return tenant

class StoreManager:
    """Clase para gestionar la creación de tiendas y usuarios."""

    def __init__(self, stores_data, tenant_instance):
        self.stores_data = stores_data
        self.tenant_instance = tenant_instance

    def create_store(self, data):
        store_type = 'tienda' if data['store_type'] == 'T' else 'almacen'
#        username = f"{store_type}_{data['name'].replace(' ', '_').lower()}"
#        user, created = User.objects.get_or_create(username=username, defaults={'password': make_password(username)})
#        Profile.objects.get_or_create(user=user, tenant=self.tenant_instance)

#        if not created:  # If the user already exists, you may want to update the password
#            user.password = make_password(username)  # Set the password
#            user.save()

        Store.objects.get_or_create(**data, tenant=self.tenant_instance)

    def create_stores(self):
        for data in self.stores_data:
            self.create_store(data)


class ProductManager:
    """Clase para gestionar la creación de productos."""

    def __init__(self, file_path):
        self.file_path = file_path
        self.workbook = xlrd.open_workbook(file_path)
        self.sheet = self.workbook.sheet_by_index(0)

    def clean_price(self, value):
            return Decimal(value.replace('$', '').replace(',', ''))

    def process_row(self, row_values):
        code = str(row_values[0])
        name = row_values[1].replace('anven', '').replace('wahl', '').replace('obelli', '').lower().strip()


        purchase_price = self.clean_price(row_values[2])
        unit_sale_price = self.clean_price(row_values[3])
        wholesale_sale_price = self.clean_price(row_values[4]) if row_values[4] else None
        wholesale_sale_price = wholesale_sale_price if unit_sale_price != wholesale_sale_price else None
        min_wholesale_quantity = 3 if wholesale_sale_price else None

        # Procesar marca
        brand_name = row_values[8].replace('.', '').replace(',', '').replace('- Sin Departamento -', 'NA').strip().title()
        if len(brand_name) <= 2:
            brand_name = brand_name.upper()
        name = name.replace(brand_name.lower(), '').strip().capitalize()
        # Crear objetos relacionados
        brand, _ = Brand.objects.get_or_create(name=brand_name)



        # Datos del producto
        product_data = {
            'code': code,
            'name': name,
            'purchase_price': purchase_price,
            'unit_sale_price': unit_sale_price,
            'wholesale_sale_price': wholesale_sale_price,
            'min_wholesale_quantity': min_wholesale_quantity,
        }

        # Crear el producto
        product, created = Product.objects.get_or_create(
                    code=code,
                    defaults={**product_data, 'brand': brand}
                )

        StoreProduct.objects.filter(product=product).update(stock=10)

    def create_products(self):
        # Use tqdm to create a progress bar for the row processing
        for row_idx in tqdm(range(1, self.sheet.nrows), desc="Creating Products", unit="product"):
            row_values = self.sheet.row_values(row_idx)        
            self.process_row(row_values)


def run():
    """Función principal que será ejecutada por runscript"""
    data_stores = [
        {'name': 'Casa', 'store_type': 'A'}, {'name': 'Victoria 1', 'store_type': 'A'},
        {'name': 'Victoria 2', 'store_type': 'A'}, {'name': 'Rayon', 'store_type': 'A'},
        {'name': 'Casa', 'store_type': 'T'}, {'name': 'Victoria 1', 'store_type': 'T'},
        {'name': 'Victoria 2', 'store_type': 'T'}, {'name': 'Rayon', 'store_type': 'T'}
    ]

    products_file_path = 'scripts/import_data/said_store/inv 300924.xls'

    tenant = TenantManager('Tienda said')
    tenant_instance = tenant.create_tenant()

    # Crear managers y ejecutar los procesos
    store_manager = StoreManager(data_stores, tenant_instance)
    product_manager = ProductManager(products_file_path)

    # Ejecutar la creación de tiendas y productos
    store_manager.create_stores()
    product_manager.create_products()
