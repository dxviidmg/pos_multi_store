from tenants.models import Tenant
from products.models import Store, StoreProduct
from logs.models import StoreProductLog
from tqdm import tqdm


def run():
    store = Store.objects.get(id=265)
    sps = StoreProduct.objects.filter(store=store)

    for sp in tqdm(
                sps, desc="checking Products", unit="product"
            ):
        logs = StoreProductLog.objects.filter(store_product=sp, movement='MA').order_by('id')

        if len(logs) < 2:
            continue

        l1 = logs[0]
        l2 = logs[1]

        if l1.calculate_difference() != l2.calculate_difference():
            continue

        print(logs)


