from celery import shared_task
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.db.models import Count
from django.db.models.functions import TruncMonth, ExtractHour, ExtractWeekDay

from .models import Sale, Payment
from .serializers import SaleAuditSerializer
from products.models import Store


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


# ============================================================
#   2) VENTAS POR MES
# ============================================================
@shared_task(bind=True)
def get_sales_by_month(self, store_ids):
    try:
        today = now()

        # ========= QUERY OPTIMIZADA =========
        sales = (
            Sale.objects.filter(
                store_id__in=store_ids,
                created_at__year=today.year,
                is_canceled=False
            )
            .annotate(month=TruncMonth("created_at"))
            .values("store_id", "month")
            .annotate(count=Count("id"))
            .order_by("store_id", "month")
        )

        # Inicialización eficiente
        store_sales = {sid: [0] * 12 for sid in store_ids}

        for s in sales:
            store_sales[s["store_id"]][s["month"].month - 1] = s["count"]

        stores = {s.id: s.get_full_name() for s in Store.objects.filter(id__in=store_ids)}

        colors = ["blue", "red", "yellow", "green"]
        datasets = []

        for i, sid in enumerate(store_ids):
            datasets.append({
                "label": stores[sid],
                "data": store_sales[sid],
                "borderColor": colors[i % 4],
                "backgroundColor": colors[i % 4],
            })

        # Promedio mensual (100% SQL hubiera sido más feo de leer, así está bien)
        num = len(store_ids)
        monthly_avg = [
            sum(store_sales[sid][i] for sid in store_ids) / num
            for i in range(12)
        ]

        if num > 1:
            datasets.append({
                "label": "Promedio",
                "data": monthly_avg,
                "borderColor": "black",
                "backgroundColor": "black",
            })

        return datasets

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


# ============================================================
#   3) VENTAS POR DÍA DE LA SEMANA
# ============================================================
@shared_task(bind=True)
def get_sales_by_weekday(self, store_ids):
    try:
        now_dt = now()
        start_dt = now_dt - timedelta(days=28)

        sales = (
            Sale.objects.filter(
                store_id__in=store_ids,
                created_at__range=(start_dt, now_dt),
                is_canceled=False
            )
            .annotate(weekday=ExtractWeekDay("created_at") - 1)
            .values("store_id", "weekday")
            .annotate(count=Count("id"))
            .order_by("store_id", "weekday")
        )

        store_sales = {sid: [0] * 7 for sid in store_ids}

        for s in sales:
            wd = s["weekday"] or 0
            store_sales[s["store_id"]][wd] = s["count"] / 4

        stores = {s.id: s.get_full_name() for s in Store.objects.filter(id__in=store_ids)}
        colors = ["blue", "red", "yellow", "green"]
        datasets = []

        for i, sid in enumerate(store_ids):
            datasets.append({
                "label": stores[sid],
                "data": store_sales[sid],
                "borderColor": colors[i % 4],
                "backgroundColor": colors[i % 4],
            })

        # Promedio por día
        num = len(store_ids)
        weekly_avg = [
            sum(store_sales[sid][i] for sid in store_ids) / num
            for i in range(7)
        ]

        if num > 1:
            datasets.append({
                "label": "Promedio",
                "data": weekly_avg,
                "borderColor": "black",
                "backgroundColor": "black",
            })

        return datasets

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


# ============================================================
#   4) VENTAS POR HORA
# ============================================================
@shared_task(bind=True)
def get_sales_by_hour(self, store_ids):
    try:
        now_dt = now()
        start_dt = now_dt - timedelta(days=28)

        sales = (
            Sale.objects.filter(
                store_id__in=store_ids,
                created_at__range=(start_dt, now_dt),
                is_canceled=False
            )
            .annotate(hour=ExtractHour("created_at"))
            .values("store_id", "hour")
            .annotate(count=Count("id"))
            .order_by("store_id", "hour")
        )

        store_sales = {sid: [0] * 24 for sid in store_ids}

        for s in sales:
            h = s["hour"] or 0
            store_sales[s["store_id"]][h] = s["count"] / 4

        stores = {s.id: s.get_full_name() for s in Store.objects.filter(id__in=store_ids)}
        colors = ["blue", "red", "yellow", "green"]
        datasets = []

        for i, sid in enumerate(store_ids):
            datasets.append({
                "label": stores[sid],
                "data": store_sales[sid],
                "borderColor": colors[i % 4],
                "backgroundColor": colors[i % 4],
            })

        num = len(store_ids)
        hourly_avg = [
            sum(store_sales[sid][i] for sid in store_ids) / num
            for i in range(24)
        ]

        if num > 1:
            datasets.append({
                "label": "Promedio",
                "data": hourly_avg,
                "borderColor": "black",
                "backgroundColor": "black",
            })

        return datasets

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


# ============================================================
#   5) PORCENTAJE DE VENTAS POR TIENDA
# ============================================================
@shared_task(bind=True)
def get_sales_percentage(self, store_ids):
    try:
        now_dt = now()
        start_dt = now_dt - timedelta(days=28)

        sales = (
            Sale.objects.filter(
                store_id__in=store_ids,
                created_at__range=(start_dt, now_dt),
                is_canceled=False
            )
            .values("store_id")
            .annotate(count=Count("id"))
        )

        total_general = sum(s["count"] for s in sales)

        stores = {s.id: s.get_full_name() for s in Store.objects.filter(id__in=store_ids)}

        result = {
            stores[s["store_id"]]: round((s["count"] / total_general) * 100, 2)
            if total_general > 0 else 0
            for s in sales
        }

        return dict(sorted(result.items()))

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


# ============================================================
#   6) PORCENTAJE DE MÉTODOS DE PAGO
# ============================================================
@shared_task(bind=True)
def get_payment_methods_percentage(self, store_ids):
    try:
        now_dt = now()
        start_dt = now_dt - timedelta(days=30)

        sales = Sale.objects.filter(
            store_id__in=store_ids,
            created_at__range=(start_dt, now_dt),
            is_canceled=False
        )

        total_sales = sales.count()
        if total_sales == 0:
            return {}

        method_counts = (
            Payment.objects.filter(sale__in=sales)
            .values("payment_method")
            .annotate(total=Count("id"))
        )

        method_map = dict(Payment.PAYMENT_METHOD_CHOICES)

        result = {
            method_map.get(m["payment_method"], m["payment_method"]): 
            round((m["total"] / total_sales) * 100, 2)
            for m in method_counts
        }

        return dict(sorted(result.items()))

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise
