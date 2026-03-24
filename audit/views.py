from django.http import JsonResponse
from celery.result import AsyncResult
from rest_framework.views import APIView
from products.decorators import get_store
from django.utils.decorators import method_decorator
from sales.tasks import get_sales_duplicates_task
from rest_framework.response import Response
from logs.tasks import get_logs_duplicates_or_inconsistens_task, get_store_products_inconsistens_task
from products.models import Store, Product, StoreProduct, Distribution, Transfer
from django.db.models import Count, Q, F
from django.utils import timezone
from sales.models import Sale
from .tasks import get_unused_products_task


class ProductAuditView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        products = Product.objects.filter(brand__tenant=tenant)

        # 1 — Códigos repetidos
        duplicate_codes = (
            products.exclude(Q(code="") | Q(code__isnull=True))
            .values("code")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )
        duplicates = []
        duplicate_code_list = [entry["code"] for entry in duplicate_codes]
        for p in products.filter(code__in=duplicate_code_list).select_related("brand", "department").order_by("code"):
            duplicates.append({
                "code": p.code,
                "brand": p.brand.name,
                "department": p.department.name if p.department else None,
                "name": p.name,
            })

        # 2 — Costo en cero
        zero_cost = list(
            products.filter(Q(cost=0) | Q(cost__isnull=True))
            .values("code", "name")
        )

        # 3 — Precio mayoreo inconsistente
        wholesale_issues = []
        qs = products.filter(
            Q(wholesale_price__gte=F("unit_price")) |
            Q(wholesale_price__gt=0, min_wholesale_quantity__isnull=True) |
            Q(wholesale_price__gt=0, min_wholesale_quantity=0) |
            Q(min_wholesale_quantity__gt=0, wholesale_price__isnull=True) |
            Q(min_wholesale_quantity__gt=0, wholesale_price=0)
        ).distinct()
        for p in qs:
            reasons = []
            if p.wholesale_price and p.wholesale_price >= p.unit_price:
                reasons.append("mayoreo >= menudeo")
            if p.wholesale_price and p.wholesale_price > 0 and (not p.min_wholesale_quantity):
                reasons.append("tiene precio mayoreo sin cantidad mínima")
            if p.min_wholesale_quantity and p.min_wholesale_quantity > 0 and (not p.wholesale_price):
                reasons.append("tiene cantidad mínima sin precio mayoreo")
            wholesale_issues.append({
                "code": p.code,
                "name": p.name,
                "unit_price": p.unit_price,
                "wholesale_price": p.wholesale_price,
                "min_wholesale_quantity": p.min_wholesale_quantity,
                "reasons": " | ".join(reasons),
            })

        # 4 — Faltantes en tiendas
        stores = Store.objects.filter(tenant=tenant)
        total_stores = stores.count()
        missing = []
        if total_stores > 0:
            product_store_counts = (
                StoreProduct.objects.filter(store__tenant=tenant)
                .values("product_id")
                .annotate(store_count=Count("store_id"))
                .filter(store_count__lt=total_stores)
            )
            store_ids_set = set(stores.values_list("id", flat=True))
            for entry in product_store_counts:
                p = products.only("id", "name", "code").get(id=entry["product_id"])
                present_ids = set(
                    StoreProduct.objects.filter(product_id=p.id, store__tenant=tenant)
                    .values_list("store_id", flat=True)
                )
                missing_stores = list(
                    stores.filter(id__in=store_ids_set - present_ids).values_list("name", flat=True)
                )
                missing.append({
                    "code": p.code, "name": p.name,
                    "missing_in": ", ".join(missing_stores),
                })

        return Response({
            "duplicate_codes": duplicates,
            "zero_cost": zero_cost,
            "wholesale_issues": wholesale_issues,
            "missing_in_stores": missing,
        })


class ProductAuditActivityView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        task = get_unused_products_task.delay(tenant.id)
        return Response({"task": task.id})


@method_decorator(get_store(), name="dispatch")
class SalesAndLogsAuditView(APIView):
    def get(self, request):
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        store_id = request.GET.get("store_id", None)
        tenant = self.request.user.get_tenant()

        if store_id:
            store_ids = [store_id]
        else:
            stores = Store.objects.filter(tenant=tenant)
            store_ids = list(stores.values_list("id", flat=True))
        
        task1 = get_sales_duplicates_task.delay(store_ids, start_date, end_date)
        task2 = get_logs_duplicates_or_inconsistens_task.delay(store_ids, start_date, end_date)
        return Response({"task1": task1.id, "task2": task2.id})
    

@method_decorator(get_store(), name="dispatch")
class StockAuditView(APIView):
    def get(self, request):
        store_id = request.GET.get("store_id", None)
        tenant = self.request.user.get_tenant()

        if store_id:
            store_ids = [store_id]
        else:
            stores = Store.objects.filter(tenant=tenant)
            store_ids = list(stores.values_list("id", flat=True))
        
        task3 = get_store_products_inconsistens_task.delay(store_ids)
        return Response({"task3": task3.id})
    
@method_decorator(get_store(), name="dispatch")
class OwnerNotificationsView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        today = timezone.localdate()

        if request.store:
            stores = Store.objects.filter(tenant=tenant, id=request.store.id)
        else:
            stores = Store.objects.filter(tenant=tenant)

        notifications = []

        for store in stores:
            store_data = {"store": store.name}

            pending_transfers = Transfer.objects.filter(
                Q(origin_store=store) | Q(destination_store=store),
                transfer_datetime__isnull=True, distribution__isnull=True
            ).count()
            if pending_transfers:
                store_data["pending_transfers"] = pending_transfers

            pending_distributions = Distribution.objects.filter(
                Q(origin_store=store) | Q(destination_store=store),
                transfer_datetime__isnull=True
            ).count()
            if pending_distributions:
                store_data["pending_distributions"] = pending_distributions

            canceled_ids = list(Sale.objects.filter(
                store=store, is_canceled=True, created_at__date=today
            ).values_list("id", flat=True))
            if canceled_ids:
                store_data["canceled_sales"] = canceled_ids

            duplicate_ids = [
                sale.id for sale in Sale.objects.filter(
                    store=store, is_canceled=False, created_at__date=today
                ).order_by("pk")
                if sale.is_repeated()
            ]
            if duplicate_ids:
                store_data["duplicate_sales"] = duplicate_ids

            # Solo incluir si tiene algo además del nombre
            if len(store_data) > 1:
                notifications.append(store_data)

        return Response(notifications)


# Create your views here.
class TaskResultView(APIView):
    def get(self, request, task_id):
        result = AsyncResult(task_id)
        
        response_data = {
            "task_id": task_id,
            "status": result.status,
        }
        
        if result.ready():
            if result.successful():
                response_data["result"] = result.result
            else:
                error_info = result.info
                response_data["error"] = {
                    "type": type(error_info).__name__,
                    "message": str(error_info)
                } if error_info else "Unknown error"
        else:
            info = result.info or {}
            response_data["info"] = info
            if "percent" in info:
                response_data["percent"] = info["percent"]
        
        return JsonResponse(response_data)