from products.models import Product

def run():
    products = Product.objects.all()

    for product in products:


        tiene_minusculas = any(c.islower() for c in product.code)
#        print(tiene_minusculas)  # True

        if tiene_minusculas:
            print(product.code, product.brand.tenant)