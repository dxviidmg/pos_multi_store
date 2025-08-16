from celery import shared_task
from datetime import datetime
from .models import Sale
from django.utils.timezone import now


@shared_task
def delete_sales_duplicates():
    today = now().date()

    sales = Sale.objects.filter(created_at__date=today)

    for sale in sales:
        sale.revert_stock_and_delete()