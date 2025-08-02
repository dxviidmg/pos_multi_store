from celery import shared_task
from .models import StoreProduct
from django.db.models import Sum
from .serializers import StoreProductForStockSerializer

@shared_task
def get_store_products_task(store_id):
    queryset = StoreProduct.objects.filter(store_id=store_id)
    serializer = StoreProductForStockSerializer(queryset, many=True)
    data = serializer.data  # esto es una lista de dicts, lista para serializar

    return data
