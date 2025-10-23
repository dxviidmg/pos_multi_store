from celery import shared_task
from datetime import datetime
from .models import Sale
from django.utils.timezone import now
from .serializers import SaleAuditSerializer
from products.models import Store
from datetime import date
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from datetime import datetime

@shared_task
def delete_sales_duplicates():
    today = now().date()

    sales = Sale.objects.filter(created_at__date=today)

    for sale in sales:
        sale.revert_stock_and_delete()


@shared_task(bind=True)
def get_sales_duplicates_task(self, store_ids, start_date, end_date):    
    try:

        self.update_state(
            state="PROGRESS",
            meta={
                "percent": 0,
                "total": 0
            }
        )
                
        sales = Sale.objects.filter(
            store_id__in=store_ids,
            created_at__date__range=(start_date, end_date)
        )

        total = sales.count()
        if total == 0:
            self.update_state(state="PROGRESS", meta={"percent": 100, "total": 0})
            return []

        self.update_state(
            state="PROGRESS",
            meta={
                "percent": 1,
                "total": 0,
                "total": total
            }
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
def get_sales_current_year(self, store_ids):    
    today = datetime.now()


    try:
        sales = (
            Sale.objects.filter(
                store_id__in=store_ids,
                created_at__year=today.year,
                is_canceled=False
            )
            .annotate(month=TruncMonth("created_at"))
            .values("store_id", "month")
            .annotate(total_amount=Sum("total"))
            .order_by("store_id", "month")
        )

        # 🔹 Estructurar los resultados en un diccionario por tienda
        store_sales = {store_id: [0] * 12 for store_id in store_ids}

        for s in sales:
            month_index = s["month"].month - 1
            store_sales[s["store_id"]][month_index] = s["total_amount"] or 0

        datasets = []

        colors = ["red", "blue", "green", "yellow", "purple"]
        stores = Store.objects.filter(id__in=store_ids).only("id", "name")
        for i, store in enumerate(stores):
            datasets.append({
                "label": store.get_full_name(),
                "data": store_sales[store.id],
                "borderColor": colors[i],
                "backgroundColor": colors[i]
            })

        num_stores = len(store_sales)
        monthly_averages = [
            (sum(month[i] for month in store_sales.values()) / num_stores) if num_stores > 0 else 0
            for i in range(12)
        ]
        datasets.append({
            "label": "Promedio",
            "data": monthly_averages,
            "borderColor": "black",
            "backgroundColor": "gray"
        })

        return datasets

    except Exception as e:
        print(e)
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise