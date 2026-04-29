from celery import shared_task
from .models import StoreProduct, Store
from .serializers import StoreProductForStockSerializer, TransferSerializer

@shared_task
def get_store_products_task(tenant_id, start_date, end_date):

    queryset = StoreProduct.objects.filter(store_tenant_id=tenant_id)
    serializer = StoreProductForStockSerializer(queryset, many=True)
    data = (serializer.data)
    return data


@shared_task
def get_stock_verification_dashboard(store_ids):
    stores_qs = Store.objects.filter(id__in=store_ids).only("id", "name")
    stores = {s.id: s.name for s in stores_qs}

    total_store_products = StoreProduct.objects.filter(store_id__in=store_ids).count()

    store_products = (
        StoreProduct.objects
        .filter(store_id__in=store_ids, requires_stock_verification=True)
        .select_related("product__brand", "store")
        .values(
            "id", "stock", "store_id",
            "product__code", "product__name", "product__brand__name",
        )
        .order_by("store_id", "product__name")
    )

    return {
        "store_products": [
            {
                "code": sp["product__code"],
                "product_name": sp["product__name"],
                "brand": sp["product__brand__name"],
                "stock": sp["stock"],
                "store_name": stores.get(sp["store_id"], ""),
            }
            for sp in store_products
        ],
        "stores": [{"name": name} for name in stores.values()],
        "total": len(store_products),
        "total_store_products": total_store_products,
    }