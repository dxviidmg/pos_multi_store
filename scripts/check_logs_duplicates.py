from products.models import StoreProduct, Product
from tqdm import tqdm
from logs.models import StoreProductLog
from tenants.models import Tenant

from datetime import datetime

#Fecha 7 de oct
def run():
    store_products_logs = StoreProductLog.objects.filter(
        created_at__gte=datetime(2025, 10, 15)
    ).order_by("id")

    print(len(store_products_logs))

    for index, store_products_log in enumerate(
        tqdm(store_products_logs, desc="Procesando", unit="item")
    ):
        if store_products_log.is_repeated():
            print(
                store_products_log.store_product,
                store_products_log.created_at,
                store_products_log.store_product.product.code,
            )