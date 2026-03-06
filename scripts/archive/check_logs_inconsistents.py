from products.models import StoreProduct, Product
from tqdm import tqdm
from logs.models import StoreProductLog
from tenants.models import Tenant
import pandas as pd
from datetime import datetime


def run():
    store_products_logs = StoreProductLog.objects.all().order_by('id')
#    start = 27127 + 7633 + 98987
#    store_products_logs = store_products_logs[start:]

    store_products_logs = StoreProductLog.objects.filter(created_at__gte=datetime(2025, 10, 15)).order_by('id')
#    store_products_logs = store_products_logs[6879:]
#    store_products_logs = StoreProductLog.objects.filter(id=40455)

    data = []
    ids = []
    for store_products_log in tqdm(store_products_logs, desc="Procesando", unit="Log"):
        if not store_products_log.is_consistent():
            sp = store_products_log.store_product

            if sp.id in ids:
                continue

            ids.append(sp.id)
            logs_by_product = (
                StoreProductLog.objects
                .filter(store_product=sp)
                .order_by("pk")  # importante: en orden ascendente
                .values_list("previous_stock", "updated_stock")
            )

            difference_total = 0
            previous_updated_stock = None

            for previous_stock, updated_stock in logs_by_product:
                if previous_updated_stock is not None:
                    difference_total += abs(previous_stock - previous_updated_stock)
                previous_updated_stock = updated_stock

            aux = {
                "tenant": store_products_log.store_product.store.tenant.name,
                "Código": store_products_log.store_product.product.code,
                "Nombre": store_products_log.store_product.product.name,
                "Tienda": store_products_log.store_product.store.name,
                "Tipo de tienda": store_products_log.store_product.store.get_store_type_display(),
                "Discrepancia": difference_total,
                "Fecha": store_products_log.created_at.replace(tzinfo=None),

            }

            print(aux)
            data.append(aux)

    df = pd.DataFrame(data)
    df.to_excel(f"Productos con logs erroneos.xlsx", index=False)
