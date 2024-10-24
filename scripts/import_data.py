from products.models import Store, Product, Brand, Category
from django.contrib.auth.models import User
import xlrd


data_stores = [{'name': 'Casa', 'store_type': 'A'}, {'name': 'Victoria 1', 'store_type': 'A'}, {'name': 'Victoria 2', 'store_type': 'A'}, {'name': 'Rayon', 'store_type': 'A'}, {'name': 'Casa', 'store_type': 'T'}, {'name': 'Victoria 1', 'store_type': 'T'}, {'name': 'Victoria 2', 'store_type': 'T'}, {'name': 'Rayon', 'store_type': 'T'},]
data_products = [{'name': 'Producto 1', 'public_sale_price': 10, 'purchase_price': 8}, {'name': 'Producto 2', 'public_sale_price': 20, 'purchase_price': 16}, {'name': 'Producto 3', 'public_sale_price': 30, 'purchase_price': 24}]


def create_stores():
    for data in data_stores:
        username = data['name'].replace(" ", "_") + '_'+data['store_type']
        user, created = User.objects.get_or_create(username=username)
        print(user)
        user.set_password(username)
        user.save()
        Store.objects.get_or_create(**data, manager=user)

def create_products():

    workbook = xlrd.open_workbook('scripts/import_data/said_store/inv 300924.xls')
    sheet = workbook.sheet_by_index(0)
    
    # Read the data into a list of dictionaries
    data = []
    max_length = 0
    for row_idx in range(1, sheet.nrows):
#        print(row_idx)
        row_values = sheet.row_values(row_idx)
        code = str(row_values[0])
        name = row_values[1]
        name_parts = name.split()  # Divide el nombre en partes
        category = name_parts[0]

        if category == '2':
            category = name_parts[2]
        elif category == '10':
            category = ' '.join(name_parts[:3]) 

        category = category.title() if len(category) > 2 else category.upper()

        purchase_price = row_values[2].replace('$', '').replace(',', '')
        unit_sale_price = row_values[3].replace('$', '').replace(',', '')
        wholesale_sale_price = row_values[4].replace('$', '').replace(',', '')

        if unit_sale_price == wholesale_sale_price:
            wholesale_sale_price = None
            min_wholesale_quantity = None
        else:
            min_wholesale_quantity = 3

        brand = row_values[8].replace('.', '').replace(',', '').replace('- Sin Departamento -', 'NA')

        brand = brand.title() if len(brand) > 2 else brand.upper()


#        print(row_values)

        brand, created = Brand.objects.get_or_create(name=brand)
        category, created = Category.objects.get_or_create(name=category)

        data = {
            'code': code,
            'name': name,
            'purchase_price': purchase_price,
            'unit_sale_price': unit_sale_price,
            'wholesale_sale_price': wholesale_sale_price,
            'min_wholesale_quantity': min_wholesale_quantity
        }
        Product.objects.get_or_create(**data, brand=brand, category=category)
#        print(data)


def run():
#    create_stores()
    create_products()
