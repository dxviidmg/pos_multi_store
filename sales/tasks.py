from datetime import datetime, timedelta

from celery import shared_task
from django.db.models import Count, DecimalField, F, Q, QuerySet, Sum
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncMonth
from django.utils.timezone import now

from products.models import Brand, Product, Store
from .models import Sale, Payment
from .serializers import SaleAuditSerializer

# ============================================================
#   1) DUPLICADOS DE VENTAS
# ============================================================
@shared_task(bind=True)
def get_sales_duplicates_task(self, store_ids, start_date, end_date):
    try:
        sales = Sale.objects.filter(
            store_id__in=store_ids,
            created_at__date__range=(start_date, end_date)
        ).only("id")  # optimización: no cargar campos innecesarios

        total = sales.count()
        self.update_state(state="PROGRESS", meta={"percent": 0, "total": total})

        if total == 0:
            return []

        ids = []
        update_every = max(total // 20, 1)

        for i, sale in enumerate(sales.iterator(chunk_size=500), start=1):
            if sale.is_repeated():  # no se puede optimizar porque es lógica del usuario
                ids.append(sale.id)

            if i % update_every == 0 or i == total:
                percent = int((i / total) * 100)
                self.update_state(
                    state="PROGRESS",
                    meta={"percent": percent, "total": total, "counter": len(ids)},
                )

        serializer = SaleAuditSerializer(
            Sale.objects.filter(id__in=ids),
            many=True
        )

        return list(serializer.data)

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@shared_task(bind=True)
def get_sales_for_dashboard(self, store_ids, year, month):
    try:
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})
        if isinstance(store_ids, QuerySet):
            store_ids = list(store_ids.values_list("id", flat=True))

        store_ids = [int(sid) for sid in store_ids]

        self.update_state(state='PROGRESS', meta={'current': 10, 'total': 100})

        # Traer stores primero (más rápido)
        stores_qs = Store.objects.filter(id__in=store_ids).only("id", "name")
        stores = {s.id: s.name for s in stores_qs}

        self.update_state(state='PROGRESS', meta={'current': 30, 'total': 100})

        # Usar values() en lugar de only() para evitar instancias de modelo
        sales_filter = {
            "store_id__in": store_ids,
            "created_at__year": year,
            "is_canceled": False
        }

        if month != '0':
            sales_filter["created_at__month"] = month

        sales = Sale.objects.filter(**sales_filter).values("store_id", "created_at", "total")

        self.update_state(state='PROGRESS', meta={'current': 70, 'total': 100})

        sales_data = [
            {
                "store_id": sale["store_id"],
                "store_name": stores.get(sale["store_id"], ""),
                "created_at": sale["created_at"].isoformat(),
                "total": float(sale["total"]),
            }
            for sale in sales
        ]

        self.update_state(state='PROGRESS', meta={'current': 90, 'total': 100})

        response = {
            "stores": [
                {"id": sid, "name": name}
                for sid, name in stores.items()
            ],
            "sales": sales_data
        }

        return response

    except Exception as e:
        print(e)
        raise


@shared_task
def get_cancellations_dashboard(store_ids, year, month):
    stores_qs = Store.objects.filter(id__in=store_ids).only("id", "name")
    stores = {s.id: s.name for s in stores_qs}

    base_filters = Q(store_id__in=store_ids, created_at__year=year)
    if month != '0':
        base_filters &= Q(created_at__month=month)

    total_sales = Sale.objects.filter(base_filters, is_canceled=False, reservation_in_progress=False).count()

    sales = Sale.objects.filter(base_filters & (Q(is_canceled=True) | Q(has_return=True))).values(
        "id", "total", "created_at", "store_id",
        "is_canceled", "has_return", "reason_cancel", "reason_return"
    ).order_by("-created_at")

    return {
        "sales": [
            {
                "id": s["id"],
                "total": float(s["total"]),
                "created_at": s["created_at"].isoformat(),
                "store_name": stores.get(s["store_id"], ""),
                "is_canceled": s["is_canceled"],
                "has_return": s["has_return"],
                "reason_cancel": s["reason_cancel"],
                "reason_return": s["reason_return"],
            }
            for s in sales
        ],
        "stores": [{"name": name} for name in stores.values()],
        "total_sales": total_sales,
    }


@shared_task
def get_products_dashboard(tenant_id, store_ids, year, month):
    from .models import ProductSale

    sale_filters = Q(sale__store_id__in=store_ids, sale__is_canceled=False, sale__reservation_in_progress=False, sale__created_at__year=year)
    if month != '0':
        sale_filters &= Q(sale__created_at__month=month)

    # Total unidades vendidas
    total_qty = ProductSale.objects.filter(sale_filters).aggregate(total=Sum("quantity"))["total"] or 0

    # Top 10 productos más vendidos
    top_products = (
        ProductSale.objects.filter(sale_filters)
        .values("product__name", "product__code", "product__brand__name")
        .annotate(quantity_sold=Sum("quantity"))
        .order_by("-quantity_sold")[:10]
    )

    # Top 10 marcas
    top_brands = (
        ProductSale.objects.filter(sale_filters)
        .values("product__brand__name")
        .annotate(
            quantity_sold=Sum("quantity"),
            product_count=Count("product", distinct=True),
        )
        .order_by("-quantity_sold")[:10]
    )

    # 10 productos menos vendidos (con al menos 1 venta)
    worst_products = (
        ProductSale.objects.filter(sale_filters)
        .values("product__name", "product__code", "product__brand__name")
        .annotate(quantity_sold=Sum("quantity"))
        .order_by("quantity_sold")[:10]
    )

    # Productos con ventas en el periodo
    products_with_sales = ProductSale.objects.filter(sale_filters).values("product").distinct().count()
    total_products = Product.objects.filter(brand__tenant_id=tenant_id).count()
    total_brands = Brand.objects.filter(tenant_id=tenant_id).count()

    def pct(qty):
        return round(qty / total_qty * 100, 1) if total_qty else 0

    return {
        "top_products": [
            {"name": p["product__name"], "code": p["product__code"], "brand_name": p["product__brand__name"], "percentage": pct(p["quantity_sold"])}
            for p in top_products
        ],
        "top_brands": [
            {"name": b["product__brand__name"], "percentage": pct(b["quantity_sold"]), "product_count": b["product_count"]}
            for b in top_brands
        ],
        "worst_products": [
            {"name": p["product__name"], "code": p["product__code"], "brand_name": p["product__brand__name"], "percentage": pct(p["quantity_sold"])}
            for p in worst_products
        ],
        "summary": {
            "total_products": total_products,
            "total_brands": total_brands,
            "products_without_sales": total_products - products_with_sales,
        },
    }
