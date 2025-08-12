from celery import shared_task
from .models import StoreProduct, Store
from .serializers import StoreProductForStockSerializer

@shared_task
def get_store_products_task(store_id):
    queryset = StoreProduct.objects.filter(store_id=store_id)
    serializer = StoreProductForStockSerializer(queryset, many=True)
    data = (serializer.data)
    return data


@shared_task
def calculate_store_investments(tenant):
    stores = Store.objects.filter(tenant=tenant)

    data = []
    for store in stores:
        data.append({"store": store.id, "investment": store.get_investment()})

#    queryset = StoreProduct.objects.filter(store_id=store_id)
#    serializer = StoreProductForStockSerializer(queryset, many=True)
#    data = (serializer.data)
    return data

