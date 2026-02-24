from products.models import Product


def run():
    id_tenant = input('Id tenant')
    products = Product.objects.filter(brand__tenant__id=id_tenant)

    for product in products:
        stock = product.get_stock()


