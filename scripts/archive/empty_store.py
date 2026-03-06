from products.models import Product, StoreProduct
from logs.models import StoreProductLog

def run():
    id = input('Id de la store: ')
    sps = StoreProduct.objects.filter(store__id=id).exclude(stock=0)
    
    
    print(len(sps))
    for i, sp in enumerate(sps):
        print(i, sp, sp.product.code)

        spls = StoreProductLog.objects.filter(store_product=sp)

        sp.stock = 0
        sp.save()
        spls.delete()
