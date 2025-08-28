from products.models import Product

def run():
    products = Product.objects.all()

    for product in products:



        if "'" in product.code:
            print(product.code, product.brand.tenant)