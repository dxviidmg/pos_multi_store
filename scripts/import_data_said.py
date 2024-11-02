from products.models import Store, Product, Brand, StoreProduct
from django.contrib.auth.models import User
import xlrd
from decimal import Decimal
from tqdm import tqdm 
from django.contrib.auth.hashers import make_password


class StoreManager:
    """Clase para gestionar la creación de tiendas y usuarios."""

    def __init__(self, stores_data):
        self.stores_data = stores_data

    def create_store(self, data):
        username = f"{data['store_type'].lower()}_{data['name'].replace(' ', '_')}"
        user, created = User.objects.get_or_create(username=username, defaults={'password': make_password(username)})

        if not created:  # If the user already exists, you may want to update the password
            user.password = make_password(username)  # Set the password
            user.save()

        Store.objects.get_or_create(**data, manager=user)

    def create_stores(self):
        for data in self.stores_data:
            self.create_store(data)


class ProductManager:
    """Clase para gestionar la creación de productos."""

    def __init__(self, file_path):
        self.file_path = file_path
        self.workbook = xlrd.open_workbook(file_path)
        self.sheet = self.workbook.sheet_by_index(0)

    def process_row(self, row_values):
        code = str(row_values[0])
        name = row_values[1]

        # Procesar precios y cantidades
        purchase_price = Decimal(row_values[2].replace('$', '').replace(',', ''))
        unit_sale_price = Decimal(row_values[3].replace('$', '').replace(',', ''))
        wholesale_sale_price = Decimal(row_values[4].replace('$', '').replace(',', '')) if row_values[4] else None
        wholesale_sale_price = wholesale_sale_price if unit_sale_price != wholesale_sale_price else None
        min_wholesale_quantity = 3 if wholesale_sale_price else None

        # Procesar marca
        brand_name = row_values[8].replace('.', '').replace(',', '').replace('- Sin Departamento -', 'NA')
        brand_name = brand_name.title() if len(brand_name) > 2 else brand_name.upper()

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

    # Crear managers y ejecutar los procesos
    store_manager = StoreManager(data_stores)
    product_manager = ProductManager(products_file_path)

    # Ejecutar la creación de tiendas y productos
    store_manager.create_stores()
    product_manager.create_products()
