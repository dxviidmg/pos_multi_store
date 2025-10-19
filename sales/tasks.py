from celery import shared_task
from datetime import datetime
from .models import Sale
from django.utils.timezone import now
from .serializers import SaleSerializer
from products.models import Store


@shared_task
def delete_sales_duplicates():
    today = now().date()

    sales = Sale.objects.filter(created_at__date=today)

    for sale in sales:
        sale.revert_stock_and_delete()


@shared_task(bind=True)
def get_sales_duplicates(self, tenant_id, start_date, end_date):    
    try:

        self.update_state(
            state="PROGRESS",
            meta={
                "percent": 1,
                "total": 0
            }
        )
                
        stores = Store.objects.filter(tenant=tenant_id)
        sales = Sale.objects.filter(
            store__in=stores,
            created_at__date__range=(start_date, end_date)
        )

        print(sales)

        total = sales.count()
        if total == 0:
            self.update_state(state="PROGRESS", meta={"percent": 100, "total": 0})
            return []

        duplicate_ids = []

        for i, sale in enumerate(sales):
            if sale.is_duplicate():
                duplicate_ids.append(sale.id)

            self.update_state(
                state="PROGRESS",
                meta={
                    "percent": int((i + 1) / total * 100),
                    "total": total
                }
            )

        duplicated_sales = Sale.objects.filter(id__in=duplicate_ids)
        serializer = SaleSerializer(duplicated_sales, many=True)

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        return {"error": str(e)}