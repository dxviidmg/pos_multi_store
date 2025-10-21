from products.models import Product, StoreProduct


def run():
    id = input('Id de la store')
    sps = StoreProduct.objects.filter(store__id=id)

    for sp in sps:
        print(sp)