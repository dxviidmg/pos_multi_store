from celery import shared_task
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.db.models import Count
from django.db.models.functions import TruncMonth, ExtractHour, ExtractWeekDay

from .models import Sale, Payment
from .serializers import SaleAuditSerializer
from products.models import Store

from celery import shared_task
from django.utils.timezone import now
from django.db.models import QuerySet
import json

# ============================================================
#   1) DUPLICADOS DE VENTAS
# ============================================================
@shared_task(bind=True)
def get_sales_duplicates_task(self, store_ids, start_date, end_date):
    try:
        sales = Sale.objects.filter(
            store_id__in=store_ids,
            created_at__date__range=(start_date, end_date)
        ).only("id")  # optimización: no cargar campos innecesarios

        total = sales.count()
        self.update_state(state="PROGRESS", meta={"percent": 0, "total": total})

        if total == 0:
            return []

        ids = []
        update_every = max(total // 20, 1)

        for i, sale in enumerate(sales.iterator(chunk_size=500), start=1):
            if sale.is_repeated():  # no se puede optimizar porque es lógica del usuario
                ids.append(sale.id)

            if i % update_every == 0 or i == total:
                percent = int((i / total) * 100)
                self.update_state(
                    state="PROGRESS",
                    meta={"percent": percent, "total": total, "counter": len(ids)},
                )

        serializer = SaleAuditSerializer(
            Sale.objects.filter(id__in=ids),
            many=True
        )

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@shared_task(bind=True)
def get_sales_for_dashboard(self, store_ids, year):
    try:
        # 🔒 Asegurar que store_ids sea lista de ints (por si mandan QuerySet)
        if isinstance(store_ids, QuerySet):
            store_ids = list(store_ids.values_list("id", flat=True))

        store_ids = [int(sid) for sid in store_ids]

        sales = (
            Sale.objects
            .filter(
                store_id__in=store_ids,
                created_at__year=year,
                is_canceled=False
            )
            .only("store_id", "created_at")
        )

        stores_qs = Store.objects.filter(id__in=store_ids).only("id", "name")
        stores = {s.id: s.get_full_name() for s in stores_qs}

        sales_data = [
            {
                "store_id": sale.store_id,
                "store_name": stores.get(sale.store_id, ""),
                "created_at": sale.created_at.isoformat(),
                "total": float(sale.total),
            }
            for sale in sales
        ]

        response = {
            "stores": [
                {"id": sid, "name": name}
                for sid, name in stores.items()
            ],
            "sales": sales_data
        }

        # 🔒 Validación extra (opcional pero útil para debug)
        json.dumps(response)

        return response

    except Exception as e:
        print(e)
#        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise