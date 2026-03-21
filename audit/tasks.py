from celery import shared_task
from products.models import Product, Transfer
from sales.models import ProductSale
from logs.models import StoreProductLog


@shared_task(bind=True)
def get_unused_products_task(self, tenant_id):
    products = Product.objects.filter(brand__tenant_id=tenant_id)
    total = products.count()

    if total == 0:
        return []

    self.update_state(state="PROGRESS", meta={"percent": 10, "total": total})

    sold_ids = set(ProductSale.objects.filter(product__in=products).values_list("product_id", flat=True))
    self.update_state(state="PROGRESS", meta={"percent": 30, "total": total})

    transferred_ids = set(Transfer.objects.filter(product__in=products).values_list("product_id", flat=True))
    self.update_state(state="PROGRESS", meta={"percent": 50, "total": total})

    logged_ids = set(StoreProductLog.objects.filter(
        store_product__product__in=products
    ).values_list("store_product__product_id", flat=True))
    self.update_state(state="PROGRESS", meta={"percent": 70, "total": total})

    used_ids = sold_ids | transferred_ids | logged_ids

    unused = products.exclude(id__in=used_ids).order_by("code").values("id", "name", "code")

    self.update_state(state="PROGRESS", meta={"percent": 90, "total": total})

    return list(unused)
