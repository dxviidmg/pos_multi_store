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
    stores = Store.objects.filter(tenant=tenant_id)
    sales = Sale.objects.filter(store__in=stores, created_at__date__gte=start_date, created_at__date__lte=end_date)

    print(sales)
    total = sales.count()

    ids = []

    for i, sale in enumerate(sales):
        if sale.is_duplicate():
            ids.append(sale.id)
        
        # actualizar progreso
        self.update_state(
            state="PROGRESS",
            meta={"current": i, "total": total, "percent": int(i/total*100)}
        )

    duplicated_sales = Sale.objects.filter(id__in=ids)
    serializer = SaleSerializer(duplicated_sales, many=True)
    return serializer.data