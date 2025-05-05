from products.models import Store, StoreProduct


def run():
    id_store = input('Id de la tienda: ')

    store = Store.objects.get(id=id_store)

    sp = StoreProduct.objects.filter(store=store).exclude(stock=0)
    sp.update(stock=0)
