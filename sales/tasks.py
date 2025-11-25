from celery import shared_task
from datetime import datetime, timedelta
from .models import Sale, Payment
from django.utils.timezone import now
from .serializers import SaleAuditSerializer
from products.models import Store
from django.db.models.functions import TruncMonth
from datetime import datetime
from django.db.models.functions import ExtractHour, ExtractWeekDay
from django.db.models import Count
from django.db.models.functions import TruncMonth


@shared_task
def delete_sales_duplicates():
    today = now().date()

    sales = Sale.objects.filter(created_at__date=today)

    for sale in sales:
        sale.revert_stock_and_delete()


@shared_task(bind=True)
def get_sales_duplicates_task(self, store_ids, start_date, end_date):
    try:

        self.update_state(state="PROGRESS", meta={"percent": 0, "total": 0})

        sales = Sale.objects.filter(
            store_id__in=store_ids, created_at__date__range=(start_date, end_date)
        )

        total = sales.count()
        if total == 0:
            self.update_state(state="PROGRESS", meta={"percent": 100, "total": 0})
            return []

        self.update_state(
            state="PROGRESS", meta={"percent": 1, "total": 0, "total": total}
        )

        ids = []
        update_every = max(total // 20, 1)
        for i, sale in enumerate(sales.iterator(), start=1):
            if sale.is_repeated():
                ids.append(sale.id)

            if i % update_every == 0 or i == total:
                percent = max(int((i / total) * 99), 1)

                self.update_state(
                    state="PROGRESS",
                    meta={"percent": percent, "total": total, "counter": len(ids)},
                )

        repeated_sales = Sale.objects.filter(id__in=ids)
        serializer = SaleAuditSerializer(repeated_sales, many=True)

        self.update_state(
            state="PROGRESS",
            meta={"percent": 100, "total": total},
        )

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@shared_task(bind=True)
def get_sales_by_month(self, store_ids):
    today = datetime.now()
    try:
        sales = (
            Sale.objects.filter(
                store_id__in=store_ids,
                created_at__year=today.year,
                is_canceled=False,
            )
            .annotate(month=TruncMonth("created_at"))
            .values("store_id", "month")
            .annotate(sales_count=Count("id"))
            .order_by("store_id", "month")
        )

        # 🔹 Estructurar los resultados en un diccionario por tienda
        store_sales = {store_id: [0] * 12 for store_id in store_ids}

        for s in sales:
            month_index = s["month"].month - 1
            store_sales[s["store_id"]][month_index] = s["sales_count"] or 0

        datasets = []

        colors = ["blue", "red", "yellow", "green"]
        stores = Store.objects.filter(id__in=store_ids).only("id", "name")

        for i, store in enumerate(stores):
            datasets.append(
                {
                    "label": store.get_full_name(),
                    "data": store_sales[store.id],
                    "borderColor": colors[i],
                    "backgroundColor": colors[i],
                }
            )

        num_stores = len(store_sales)
        monthly_averages = [
            (
                (sum(month[i] for month in store_sales.values()) / num_stores)
                if num_stores > 0
                else 0
            )
            for i in range(12)
        ]

        if len(store_ids) > 1:
            datasets.append(
                {
                    "label": "Promedio",
                    "data": monthly_averages,
                    "borderColor": "black",
                    "backgroundColor": "black",
                }
            )

        return datasets


    except Exception as e:
        print(e)
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@shared_task(bind=True)
def get_sales_by_weekday(self, store_ids):
    now = datetime.now()
    one_month_ago = now - timedelta(days=28)

    try:
        # 🔹 Filtrar ventas del último mes (no canceladas)
        sales = (
            Sale.objects.filter(
                store_id__in=store_ids,
                created_at__range=[one_month_ago, now],
                is_canceled=False,
            )
            .annotate(weekday=ExtractWeekDay("created_at") - 1)
            .values("store_id", "weekday")
            .annotate(sales_count=Count("id"))
            .order_by("store_id", "weekday")
        )

        # 🔹 Inicializar estructura para los 7 días (domingo=0 ... sábado=6)
        store_sales = {store_id: [0] * 7 for store_id in store_ids}

        # 🔹 Llenar datos de cantidad de ventas por día
        for s in sales:
            weekday_index = s["weekday"]/4 or 0  # por si algún valor es None
            store_sales[s["store_id"]][weekday_index] = s["sales_count"] or 0

        datasets = []

        colors = ["blue", "red", "yellow", "green"]
        stores = Store.objects.filter(id__in=store_ids).only("id", "name")

        # 🔹 Crear dataset por tienda
        for i, store in enumerate(stores):
            datasets.append(
                {
                    "label": store.get_full_name(),
                    "data": store_sales[store.id],
                    "borderColor": colors[i % len(colors)],
                    "backgroundColor": colors[i % len(colors)],
                }
            )

        # 🔹 Calcular promedio semanal entre tiendas
        num_stores = len(store_sales)
        weekly_averages = [
            (
                (sum(day[i] for day in store_sales.values()) / num_stores)
                if num_stores > 0
                else 0
            )
            for i in range(7)
        ]

        if len(store_ids) > 1:
            datasets.append(
                {
                    "label": "Promedio",
                    "data": weekly_averages,
                    "borderColor": "black",
                    "backgroundColor": "black",
                }
            )

        return datasets
    except Exception as e:
        print(e)
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@shared_task(bind=True)
def get_sales_by_hour(self, store_ids):
    now = datetime.now()
    one_month_ago = now - timedelta(days=28)

    try:
        # 🔹 Filtrar ventas de los últimos 30 días (no canceladas)
        sales = (
            Sale.objects.filter(
                store_id__in=store_ids,
                created_at__range=[one_month_ago, now],
                is_canceled=False,
            )
            .annotate(hour=ExtractHour("created_at"))
            .values("store_id", "hour")
            .annotate(sales_count=Count("id"))
            .order_by("store_id", "hour")
        )

        # 🔹 Inicializar estructura para 24 horas
        store_sales = {store_id: [0] * 24 for store_id in store_ids}

        # 🔹 Llenar datos de cantidad de ventas por hora
        for s in sales:
            hour_index = s["hour"] or 0
            store_sales[s["store_id"]][hour_index] = s["sales_count"]/4 or 0

        datasets = []

        colors = ["blue", "red", "yellow", "green"]
        stores = Store.objects.filter(id__in=store_ids).only("id", "name")

        # 🔹 Crear dataset por tienda
        for i, store in enumerate(stores):
            datasets.append(
                {
                    "label": store.get_full_name(),
                    "data": store_sales[store.id],
                    "borderColor": colors[i % len(colors)],
                    "backgroundColor": colors[i % len(colors)],
                }
            )

        # 🔹 Calcular promedio por hora entre tiendas
        num_stores = len(store_sales)
        hourly_averages = [
            (
                (sum(day[i] for day in store_sales.values()) / num_stores)
                if num_stores > 0
                else 0
            )
            for i in range(24)
        ]

        print(hourly_averages)

        if len(store_ids) > 1:
            datasets.append(
                {
                    "label": "Promedio",
                    "data": hourly_averages,
                    "borderColor": "black",
                    "backgroundColor": "black",
                }
            )

        return datasets

    except Exception as e:
        print(e)
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@shared_task(bind=True)
def get_sales_percentage(self, store_ids):
    now = datetime.now()
    one_month_ago = now - timedelta(days=28)
    try:
        sales = (
            Sale.objects.filter(
                store_id__in=store_ids, created_at__range=[one_month_ago, now], is_canceled=False
            )
            .values("store_id")
            .annotate(sales_count=Count("id"))
        )

        # 🔹 Calcular el total general
        total_general = sum(s["sales_count"] or 0 for s in sales)

        # 🔹 Agregar el porcentaje a cada tienda
        sales_with_percentage = {}
        for s in sales:
            total = s["sales_count"] or 0
            percentage = (total / total_general * 100) if total_general > 0 else 0
            store = Store.objects.get(id=s["store_id"])
            sales_with_percentage[store.get_full_name()] = round(percentage, 2)

        return sales_with_percentage

    except Exception as e:
        print(e)
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@shared_task(bind=True)
def get_payment_methods_percentage(self, store_ids):
    now = datetime.now()
    one_month_ago = now - timedelta(days=30)

    try:
        sales = Sale.objects.filter(
            store_id__in=store_ids, created_at__range=[one_month_ago, now], is_canceled=False
        )

        # 🔹 Contar pagos por método
        method_counts = (
            Payment.objects.filter(sale__in=sales)
            .values("payment_method")
            .annotate(total=Count("id"))
        )

        # 🔹 Diccionario de códigos a nombres legibles
        payment_method_dict = dict(Payment.PAYMENT_METHOD_CHOICES)

        # 🔹 Generar diccionario con nombres legibles y conteos
        payment_percent = {
            payment_method_dict.get(
                item["payment_method"], item["payment_method"]
            ): round(item["total"] * 100 / sales.count(), 2)
            for item in method_counts
        }

        payment_percent = dict(sorted(payment_percent.items()))
        return payment_percent

    except Exception as e:
        print(e)
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise
