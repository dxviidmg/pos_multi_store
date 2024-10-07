from products.models import Store, Product

data_stores = [{'name': 'Tienda 1'}, {'name': 'Tienda 2'}, {'name': 'Tienda 3'}]
data_products = [{'name': 'Producto 1', 'price': 10}, {'name': 'Producto 2', 'price': 20}, {'name': 'Producto 3', 'price': 30}]

def run():
    for data in data_stores:
        Store.objects.get_or_create(**data)


    for data in data_products:

        Product.objects.get_or_create(**data)
        print(data)

