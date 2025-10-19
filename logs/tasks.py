from products.models import Store, StoreProduct
from .models import StoreProductLog
from .serializers import StoreProductLogSerializer
from celery import shared_task
from products.serializers import StoreProductBaseSerializer

@shared_task(bind=True)
def get_logs_duplicates_or_inconsistens_task(self, tenant_id, start_date, end_date):
    try:
        stores = Store.objects.filter(tenant=tenant_id)
        logs = StoreProductLog.objects.filter(
            store_product__store__in=stores,
            created_at__date__range=(start_date, end_date),
        )

        total = logs.count()
        ids = []

        for i, log in enumerate(logs):
            if log.is_duplicate() or not log.is_consistent():
                ids.append(log.id)

            self.update_state(
                state="PROGRESS",
                meta={"percent": int((i + 1) / total * 100), "total": total, "i": i},
            )

        duplicated_sales = StoreProductLog.objects.filter(id__in=ids)
        serializer = StoreProductLogSerializer(duplicated_sales, many=True)

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        return {"error": str(e)}


@shared_task(bind=True)
def get_store_products_inconsistens_task(self, tenant_id):
    try:
        store_products = StoreProduct.objects.filter(store__tenant_id=tenant_id)
        total = store_products.count()
        ids = []

        for i, store_product in enumerate(store_products):
            last_store_product_log = StoreProductLog.objects.filter(store_product=store_product).order_by('id').last()

            self.update_state(
                state="PROGRESS",
                meta={"percent": int((i + 1) / total * 100), "total": total, "i": i},
            )

            if not last_store_product_log:
                continue
            
            if store_product.stock == last_store_product_log.updated_stock or store_product.stock > 0:
                continue

            ids.append(store_product.id)

        
        store_products_inconsistents = StoreProduct.objects.filter(id__in=ids)

        
        serializer = StoreProductBaseSerializer(store_products_inconsistents, many=True)
        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        return {"error": str(e)}