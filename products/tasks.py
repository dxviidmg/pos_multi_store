from celery import shared_task
from .models import StoreProduct, Store, Transfer
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

@shared_task
def get_pending_transfers_dashboard(store_ids):
    stores_qs = Store.objects.filter(id__in=store_ids).only("id", "name")
    stores = {s.id: s.name for s in stores_qs}

    tranfers = (
        Transfer.objects
        .filter(destination_store__in=store_ids, transfer_datetime=None, distribution=None)
        .select_related("destination_store")
        .values(
            "id", "quantity", "destination_store_id", "created_at",
            "product__name", "product__brand__name"
        )
        .order_by("destination_store", "created_at")
    )

    return {
        "transfers": [
            {
                "quantity": t["quantity"],
                "destination_store": stores.get(t["destination_store_id"], ""),
                "created_at": t["created_at"],
                "product": t["product__name"],
                "brand": t["product__brand__name"],
            }
            for t in tranfers
        ],
        "stores": [{"name": name} for name in stores.values()],
        "total": len(tranfers),
    }