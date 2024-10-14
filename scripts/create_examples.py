from products.models import Store, Product, Brand, Category
from django.contrib.auth.models import User

data_stores = [{'name': 'Tienda 1'}, {'name': 'Tienda 2'}, {'name': 'Tienda 3'}]
data_products = [{'name': 'Producto 1', 'public_sale_price': 10, 'purchase_price': 8}, {'name': 'Producto 2', 'public_sale_price': 20, 'purchase_price': 16}, {'name': 'Producto 3', 'public_sale_price': 30, 'purchase_price': 24}]


def create_stores():
    for data in data_stores:
        user, created = User.objects.get_or_create(username=data['name'])
        user.set_password(data['name'])
        user.save()
        Store.objects.get_or_create(**data, manager=user)

def create_products():
    brand, created = Brand.objects.get_or_create(name='Brand')
    category, created = Category.objects.get_or_create(name='Category')

    for data in data_products:
        Product.objects.get_or_create(**data, brand=brand, category=category, code=data['name'])
        print(data)


def run():
    create_stores()
    create_products()
