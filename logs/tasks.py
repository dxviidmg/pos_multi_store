from products.models import Store
from .models import StoreProductLog
from .serializers import StoreProductLogSerializer
from celery import shared_task


@shared_task(bind=True)
def get_logs_duplicates(self, tenant_id, start_date, end_date):
    try:
        stores = Store.objects.filter(tenant=tenant_id)
        logs = StoreProductLog.objects.filter(
            store_product__store__in=stores,
            created_at__date__range=(start_date, end_date),
        )

        total = logs.count()
        if total == 0:
            return []

        duplicate_ids = []

        for i, log in enumerate(logs):
            if log.is_duplicate():
                duplicate_ids.append(log.id)

            self.update_state(
                state="PROGRESS",
                meta={"percent": int((i + 1) / total * 100), "total": total, "i": i},
            )

        duplicated_sales = StoreProductLog.objects.filter(id__in=duplicate_ids)
        serializer = StoreProductLogSerializer(duplicated_sales, many=True)

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        return {"error": str(e)}



@shared_task(bind=True)
def get_logs_inconsistens(self, tenant_id, start_date, end_date):
    try:

        stores = Store.objects.filter(tenant=tenant_id)
        logs = StoreProductLog.objects.filter(
            store_product__store__in=stores,
            created_at__date__range=(start_date, end_date),
        )
        total = logs.count()
        if total == 0:

            return []

        duplicate_ids = []

        for i, log in enumerate(logs):
            if log.is_consistent():
                duplicate_ids.append(log.id)

            self.update_state(
                state="PROGRESS",
                meta={"percent": int((i + 1) / total * 100), "total": total, "i": i},
            )

        duplicated_sales = StoreProductLog.objects.filter(id__in=duplicate_ids)
        serializer = StoreProductLogSerializer(duplicated_sales, many=True)

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        return {"error": str(e)}
