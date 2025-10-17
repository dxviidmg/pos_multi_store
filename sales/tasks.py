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


@shared_task
def get_sales_duplicates(tenant_id):
    today = now().date()
    stores=Store.objects.filter(tenant=tenant_id)
    sales = Sale.objects.filter(store__in=stores)

    ids = []
    for sale in sales:
        if sale.is_duplicate():
            ids.append(sale.id)


    duplicated_sales = Sale.objects.filter(id__in=ids)

    serializer = SaleSerializer(duplicated_sales, many=True)

    print(serializer)
    data = (serializer.data)
    return data
