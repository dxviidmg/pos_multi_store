from products.models import StoreProduct
from .models import StoreProductLog
from .serializers import StoreProductLogAuditSerializer
from celery import shared_task
from products.serializers import StoreProductAuditSerializer
from django.db.models import OuterRef, Subquery
import time


@shared_task(bind=True)
def get_logs_duplicates_or_inconsistens_task(self, store_ids, start_date, end_date):
    try:
        # Estado inicial
        self.update_state(state="PROGRESS", meta={"percent": 0, "total": 0})

        logs_qs = StoreProductLog.objects.filter(
            store_product__store_id__in=store_ids,
            created_at__date__range=(start_date, end_date),
        )

        total = logs_qs.count()
        if total == 0:
            self.update_state(state="PROGRESS", meta={"percent": 100, "total": 0})
            return []

        self.update_state(state="PROGRESS", meta={"percent": 1, "total": total})

        ids = []
        update_every = max(total // 20, 1)

        # 🚀 Usar iterator() evita cargar todo en memoria
        for i, log in enumerate(logs_qs.iterator(), start=1):
            # Si estos métodos hacen queries, puede optimizarse más (ver nota abajo)
            if log.is_repeated() or not log.is_consistent() or log.has_negatives():
                ids.append(log.id)

            if i % update_every == 0 or i == total:
                percent = max(int((i / total) * 99), 1)
                self.update_state(
                    state="PROGRESS",
                    meta={"percent": percent, "total": total},
                )

        inconsistent_logs = StoreProductLog.objects.filter(id__in=ids)
        serializer = StoreProductLogAuditSerializer(inconsistent_logs, many=True)

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
        # Estado inicial
        self.update_state(state="PROGRESS", meta={"percent": 0, "total": 0})

        store_products = StoreProduct.objects.filter(store_id__in=store_ids)
        total = store_products.count()

        if total == 0:
            self.update_state(state="PROGRESS", meta={"percent": 100, "total": 0})
            return []

        # Subquery para obtener el último log
        last_log_subquery = StoreProductLog.objects.filter(
            store_product=OuterRef('pk')
        ).order_by('-id')

        # Anotamos el stock del último log
        store_products = store_products.annotate(
            last_log_stock=Subquery(last_log_subquery.values('updated_stock')[:1])
        )

        ids = []
        update_every = max(total // 5, 1)

        for i, sp in enumerate(store_products, start=1):
            if i % update_every == 0 or i == total:
                percent = max(int((i / total) * 99), 1)
                self.update_state(
                    state="PROGRESS",
                    meta={"percent": percent, "total": total},
                )
                time.sleep(0.5)

            # Detectar inconsistencias
            if sp.stock < 0 or (sp.last_log_stock is not None and sp.stock != sp.last_log_stock):
                ids.append(sp.id)

        # Filtrar productos inconsistentes
        store_products_inconsistents = StoreProduct.objects.filter(id__in=ids)

        serializer = StoreProductAuditSerializer(store_products_inconsistents, many=True)

        # Estado final
        self.update_state(
            state="PROGRESS",
            meta={"percent": 100, "total": total},
        )

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise