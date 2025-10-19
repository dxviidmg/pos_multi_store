from celery import shared_task
from .models import StoreProduct, Store
from .serializers import StoreProductForStockSerializer, TransferSerializer

@shared_task
def get_store_products_task(tenant_id, start_date, end_date):

    queryset = StoreProduct.objects.filter(store_tenant_id=tenant_id)
    serializer = StoreProductForStockSerializer(queryset, many=True)
    data = (serializer.data)
    return data