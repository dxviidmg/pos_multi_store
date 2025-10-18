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
    sales = Sale.objects.filter(
        store__in=stores,
        created_at__date__range=(start_date, end_date)
    )

    total = sales.count()
    if total == 0:
        return []  # No hay ventas, no vale la pena iterar

    duplicate_ids = []

    for i, sale in enumerate(sales):
        if sale.is_duplicate():
            duplicate_ids.append(sale.id)

        # actualizar progreso cada 10 registros (ajustable)
        if (i + 1) % 10 == 0 or (i + 1) == total:
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": i + 1,
                    "total": total,
                    "percent": int((i + 1) / total * 100)
                }
            )

    duplicated_sales = Sale.objects.filter(id__in=duplicate_ids)
    serializer = SaleSerializer(duplicated_sales, many=True)
    return serializer.data