from products.models import StoreProduct
from .models import StoreProductLog
from .serializers import StoreProductLogSerializer
from celery import shared_task
from products.serializers import StoreProductBaseSerializer


@shared_task(bind=True)
def get_logs_duplicates_or_inconsistens_task(self, store_ids, start_date, end_date):
    try:
        self.update_state(state="PROGRESS", meta={"percent": 0, "total": 0})
        logs = StoreProductLog.objects.filter(
            store_product__store_id__in=store_ids,
            created_at__date__range=(start_date, end_date),
        )

        total = logs.count()

        if total == 0:
            self.update_state(state="PROGRESS", meta={"percent": 100, "total": 0})
            return []

        self.update_state(state="PROGRESS", meta={"percent": 1, "total": 0})

        ids = []
        update_every = max(total // 20, 1)
        for i, log in enumerate(logs):
            if log.is_duplicate() or not log.is_consistent():
                ids.append(log.id)

            if i % update_every == 0 or i == total:
                percent = max(int((i / total) * 99), 1)

                self.update_state(
                    state="PROGRESS",
                    meta={"percent": percent, "total": total},
                )

        duplicated_sales = StoreProductLog.objects.filter(id__in=ids)
        serializer = StoreProductLogSerializer(duplicated_sales, many=True)

        self.update_state(
            state="PROGRESS",
            meta={"percent": 100, "total": total},
        )

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        return {"error": str(e)}


@shared_task(bind=True)
def get_store_products_inconsistens_task(self, store_ids):
    try:
        self.update_state(state="PROGRESS", meta={"percent": 0, "total": 0})
        store_products = StoreProduct.objects.filter(store_id__in=store_ids)
        total = store_products.count()

        if total == 0:
            self.update_state(state="PROGRESS", meta={"percent": 100, "total": 0})
            return []

        self.update_state(state="PROGRESS", meta={"percent": 1, "total": 0})

        ids = []
        update_every = max(total // 100, 1)

        for i, store_product in enumerate(store_products):
            if i % update_every == 0 or i == total:
                percent = max(int((i / total) * 99), 1)

                self.update_state(
                    state="PROGRESS",
                    meta={"percent": percent, "total": total},
                )

            last_store_product_log = (
                StoreProductLog.objects.filter(store_product=store_product)
                .order_by("id")
                .last()
            )

            if not last_store_product_log:
                continue

            if (
                store_product.stock == last_store_product_log.updated_stock
                or store_product.stock > 0
            ):
                continue

            ids.append(store_product.id)

        store_products_inconsistents = StoreProduct.objects.filter(id__in=ids)

        serializer = StoreProductBaseSerializer(store_products_inconsistents, many=True)

        self.update_state(
            state="PROGRESS",
            meta={"percent": 100, "total": total, "i": total},
        )

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        return {"error": str(e)}
