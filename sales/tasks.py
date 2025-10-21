from celery import shared_task
from datetime import datetime
from .models import Sale
from django.utils.timezone import now
from .serializers import SaleAuditSerializer
from products.models import Store


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

        for i, sale in enumerate(sales):
            if sale.is_duplicate():
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