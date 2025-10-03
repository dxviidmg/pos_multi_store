from products.models import StoreProduct, Product
from tqdm import tqdm
from logs.models import StoreProductLog
from tenants.models import Tenant


def run():
    tenant = Tenant.objects.get(id=2)
    products = Product.objects.filter(brand__tenant=tenant)
    store_products = StoreProduct.objects.filter(product__in=products).prefetch_related('store_product_logs').order_by('store')[1155:]


    for store_product in tqdm(store_products, desc="Logs", unit="Log"):
        logs = list(store_product.store_product_logs.all().order_by('id'))

        if len(logs) <= 1:
            continue

        ref = logs[0].updated_stock
        for log in logs[1:]:
            if ref != log.previous_stock:
                print('*', store_product.product.code, store_product, 'Expected:', ref, 'Found:', log.previous_stock, log.created_at.date(), log.get_description())
                # Puedes reemplazar input por logging o acumular errores en una lista
                break
            ref = log.updated_stock
                
            


#        break

#        pass
#        print(store_product)