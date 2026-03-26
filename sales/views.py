from collections import defaultdict
from datetime import datetime

import pandas as pd
from django.db import transaction
from django.db.models import Count, DecimalField, F, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from logs.models import StoreProductLog
from notifications.utils import notify_store
from products.decorators import get_store
from products.import_utils import (
    validate_store_product_columns,
    rename_store_product_columns,
    validate_quantities,
)
from products.models import CashFlow, Product, Store, StoreProduct
from .cash_summary_utils import calculate_cash_summary
from .models import Sale, ProductSale, Payment
from .serializers import SaleSerializer, SaleCreateSerializer, SaleAuditSerializer
from .tasks import get_sales_for_dashboard, get_cancellations_dashboard, get_products_dashboard

# Límites para archivos Excel
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_ROWS = 10000
ALLOWED_EXTENSIONS = ['.xlsx', '.xls']
ALLOWED_MIME_TYPES = [
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel'
]


def validate_excel_file(file_obj):
    """Valida tamaño, tipo y formato de archivo Excel"""
    if file_obj.size > MAX_FILE_SIZE:
        raise ValueError(f"Archivo muy grande. Máximo: {MAX_FILE_SIZE / 1024 / 1024}MB")
    
    import os
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extensión no permitida. Use: {', '.join(ALLOWED_EXTENSIONS)}")
    
    if hasattr(file_obj, 'content_type') and file_obj.content_type not in ALLOWED_MIME_TYPES:
        raise ValueError("Tipo de archivo no válido")
    
    return True

@method_decorator(get_store(), name="dispatch")
# Create your views here.
class SaleViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.method == "POST":
            return SaleCreateSerializer
        return SaleSerializer

    def get_queryset(self):
        store = self.request.store
        user = self.request.user

        # Obtener parámetros
        date = self.request.GET.get("date")
        reservation_in_progress = self.request.GET.get("reservation_in_progress") == "true"
        sale_id = self.request.GET.get("sale_id")
        first_name = self.request.GET.get("first_name")
        last_name = self.request.GET.get("last_name")
        is_repeatedd = self.request.GET.get("is_repeatedd") == "true"
        # Construir query base
        query = {"store": store}

        if reservation_in_progress:
            query["reservation_in_progress"] = True
        else:
            query["reservation_in_progress"] = False
            if date:
                query["created_at__date"] = date

        if sale_id:
            query["id__startswith"] = sale_id

        if user.get_role() == "seller":
            query["seller"] = user

        if first_name:
            query["client__first_name__icontains"] = first_name

        if last_name:
            query["client__last_name__icontains"] = last_name

        # Si hay búsqueda por cliente, ignorar el filtro por fecha
        if (first_name or last_name) and "created_at__date" in query:
            query.pop("created_at__date")

        queryset = Sale.objects.filter(**query).select_related(
            "store", "seller", "client"
        ).prefetch_related(
            "products_sale__product__brand",
            "payments"
        )
        
        # Optimizar para listado
        if self.action == 'list':
            queryset = queryset.only(
                'id', 'total', 'created_at', 'reservation_in_progress', 'is_canceled',
                'store__id', 'store__name',
                'seller__id', 'seller__username',
                'client__id', 'client__first_name', 'client__last_name'
            )
        
        return queryset.order_by("-id")

    def perform_create(self, serializer):
        store_products_data = self.request.data.get("store_products")
        payments_data = self.request.data.get("payments")

        reference_payment = self.request.data.get("reference_payment")
        sale_exchange = self.request.data.get("sale_exchange")

        reservation_in_progress = self.request.data.get("reservation_in_progress")

        if not store_products_data:
            return Response(
                {"detail": "store_products is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not reservation_in_progress and not payments_data:
            return Response(
                {"detail": "payment is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_store_products = []  # Lista para almacenar instancias de StoreProduct
        logs = []  # Lista para almacenar logs de StoreProductLog

        store = self.request.store
        seller = self.request.user

        # Usar una transacción para asegurar la atomicidad
        with transaction.atomic():
            for product_data in store_products_data:
                product_store = StoreProduct.objects.select_for_update().get(id=product_data["id"])
                
                # Validar stock disponible
                available_stock = product_store.calculate_available_stock()
                if available_stock < product_data["quantity"]:
                    return Response(
                        {
                            "detail": f"Stock insuficiente para {product_store.product.name}. "
                                     f"Disponible: {available_stock}, Solicitado: {product_data['quantity']}"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                
                if product_store.stock < product_data["quantity"]:
                    previous_stock = product_store.stock
                    product_store.stock = product_data["quantity"]
                    product_store.save()

                    StoreProductLog.objects.create(
                        store_product=product_store,
                        user=self.request.user,
                        previous_stock=previous_stock,
                        updated_stock=product_data["quantity"],
                        action="A"
                    )

                previous_stock = product_store.stock
                updated_stock = previous_stock - product_data["quantity"]

                # Actualizar el stock del producto
                product_store.stock = updated_stock
                updated_store_products.append(product_store)

                # Crear el log correspondiente
                logs.append(
                    StoreProductLog(
                        store_product=product_store,
                        user=seller,
                        previous_stock=previous_stock,
                        updated_stock=(
                            previous_stock if reservation_in_progress else updated_stock
                        ),
                        action="N" if reservation_in_progress else "S",
                        movement="AP" if reservation_in_progress else "VE",
                    )
                )

            # Actualizar los stocks de los productos en una sola operación
            if not reservation_in_progress:
                StoreProduct.objects.bulk_update(updated_store_products, ["stock"])
            # Guardar los logs en la base de datos
            StoreProductLog.objects.bulk_create(logs)

            # Guardar la venta y asociarla al usuario actual
            sale_instance = serializer.save(
                store=store,
                seller=seller,
                reservation_in_progress=reservation_in_progress,
            )

            # Crear las relaciones de ProductSale
            for product_data in store_products_data:
                product_store = StoreProduct.objects.get(id=product_data["id"])
                product = product_store.product

                data = {
                    "sale": sale_instance,
                    "product": product,
                    "quantity": product_data["quantity"],
                    "price": product_data["price"],
                }
                ProductSale.objects.create(**data)

            # Crear las relaciones de Payment
            for payment_data in payments_data:
                data = {
                    "sale": sale_instance,
                    "payment_method": payment_data["payment_method"],
                    "amount": payment_data["amount"],
                    "reference": (
                        reference_payment
                        if payment_data["payment_method"] != "EF"
                        else None
                    ),
                }
                Payment.objects.create(**data)

            if "id" in sale_exchange:
                created_dt = datetime.fromisoformat(sale_exchange['created_at']).date()
                today = datetime.today().date()

                if created_dt != today:
                    cash_flow_data = {
                        "amount": sale_exchange["refunded"],
                        "transaction_type": "S",
                        "concept": "Diferencia entre compra "
                        + str(sale_instance.pk)
                        + " devolución "
                        + str(sale_exchange["id"]),
                        "user": seller,
                        "store": store,
                    }
                    CashFlow.objects.create(**cash_flow_data)

        if reservation_in_progress:
            notify_store(store, store.tenant_id, {
                'event': 'reservation_created',
                'message': f'Nuevo apartado #{sale_instance.pk} en {store.name}',
            })

        if not reservation_in_progress and sale_instance.is_repeated():
            notify_store(store, store.tenant_id, {
                'event': 'duplicate_sale',
                'message': f'Posible venta duplicada #{sale_instance.pk}',
            })

        return sale_instance

    def get_object(self):
        store = self.request.store
        sale_id = self.kwargs.get("pk")  # DRF usa "pk" aunque lo sobreescribas

        try:
            sale = Sale.objects.get(id=sale_id, store=store)
            return sale
        except Sale.DoesNotExist:
            raise NotFound(detail="Sale not found for this store.")

    def perform_update(self, serializer):
        payment_data = self.request.data.get("payment")

        if not payment_data:
            return Response(
                {"detail": "payment is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Payment.objects.create(**payment_data)
        sale_instance = serializer.save()

        reservation_in_progress = self.request.data.get("reservation_in_progress")

        if not reservation_in_progress:

            store = self.request.store
            seller = self.request.user
            updated_store_products = []
            logs = []
            with transaction.atomic():

                for product_sale in sale_instance.products_sale.all():
                    product_store = StoreProduct.objects.select_for_update().get(
                        store=store, product=product_sale.product
                    )
                    previous_stock = product_store.stock
                    updated_stock = previous_stock - product_sale.quantity

                    # Actualizar el stock del producto
                    product_store.stock = updated_stock
                    updated_store_products.append(product_store)

                    # Crear el log correspondiente
                    logs.append(
                        StoreProductLog(
                            store_product=product_store,
                            user=seller,
                            previous_stock=previous_stock,
                            updated_stock=(
                                previous_stock
                                if reservation_in_progress
                                else updated_stock
                            ),
                            action="S",
                            movement="VE",
                        )
                    )

                # Actualizar los stocks de los productos en una sola operación
                if not reservation_in_progress:
                    StoreProduct.objects.bulk_update(updated_store_products, ["stock"])
                # Guardar los logs en la base de datos
                StoreProductLog.objects.bulk_create(logs)

        return sale_instance


@method_decorator(get_store(), name="dispatch")
class CashSummaryView(APIView):
    def get(self, request):
        date = request.GET.get("date")
        store = request.store

        response_data = calculate_cash_summary(store, date)

        return Response(response_data)


@method_decorator(get_store(), name="dispatch")
class SaleImportValidationView(APIView):
    def post(self, request):
        file_obj = request.FILES.get("file")

        if not file_obj:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            validate_excel_file(file_obj)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        store = self.request.store
        tenant = self.request.user.get_tenant()

        try:
            df = pd.read_excel(file_obj, nrows=MAX_ROWS)
            
            if len(df) > MAX_ROWS:
                return Response(
                    {"error": f"Demasiadas filas. Máximo: {MAX_ROWS}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            validate_store_product_columns(df)
            df = rename_store_product_columns(df)
            validate_quantities(df)

            validation_results = []
            product_quantities = (
                {}
            )  # Diccionario para rastrear existencias por código de producto

            for _, row in df.iterrows():
                row_data = row.to_dict()
                row_data["status"] = "Exitoso"

                code = row["code"]
                quantity = row["quantity"]
                try:

                    product = Product.objects.get(code=code, brand__tenant=tenant)
                except Product.DoesNotExist:
                    row_data["status"] = "Código no encontrado"
                    validation_results.append(row_data)
                    continue

                # Verificar existencias y manejar cantidades
                if code in product_quantities:
                    available_quantity = product_quantities[code]
                else:
                    store_product = StoreProduct.objects.get(
                        product=product, store=store
                    )
                    available_quantity = store_product.calculate_available_stock()
                    product_quantities[code] = available_quantity

                if available_quantity < quantity:
                    row_data["status"] = "Cantidad insuficiente"
                    product_quantities[code] = (
                        0  # Actualizar a 0 porque no hay suficiente stock
                    )
                else:
                    product_quantities[code] -= quantity

                validation_results.append(row_data)

            return Response(validation_results, status=status.HTTP_200_OK)

        except ValueError as e:
            print(e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(get_store(), name="dispatch")
class SaleImportView(APIView):
    def post(self, request):
        file_obj = request.FILES.get("file")

        if not file_obj:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            validate_excel_file(file_obj)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        tenant = self.request.user.get_tenant()
        store = self.request.store
        seller = self.request.user

        try:
            df = pd.read_excel(file_obj, nrows=MAX_ROWS)
            
            if len(df) > MAX_ROWS:
                return Response(
                    {"error": f"Demasiadas filas. Máximo: {MAX_ROWS}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            validate_store_product_columns(df)
            df = rename_store_product_columns(df)

            logs = []  # Lista para almacenar registros de StoreProductLog

            for _, row in df.iterrows():
                code = row["code"]
                quantity = row["quantity"]

                # Obtener el producto y la relación StoreProduct
                product = Product.objects.get(code=code, brand__tenant=tenant)
                store_product = StoreProduct.objects.select_for_update().get(product=product, store=store)

                previous_stock = store_product.stock
                updated_stock = previous_stock - quantity

                # Validar que el stock no sea negativo
                if updated_stock < 0:
                    raise ValueError(
                        f"Insufficient stock for product {product.name} (Code: {code})."
                    )

                # Actualizar el stock del producto
                store_product.stock = updated_stock
                store_product.save()

                # Crear el log correspondiente
                logs.append(
                    StoreProductLog(
                        store_product=store_product,
                        user=seller,
                        previous_stock=previous_stock,
                        updated_stock=updated_stock,
                        action="S",  # Acción: Salida
                        movement="VE",  # Movimiento: Venta
                    )
                )

                # Calcular el total de la venta y registrar la venta
                total = product.unit_price * quantity
                sale_instance = Sale.objects.create(
                    store=store, total=total, seller=seller
                )

                # Crear la relación ProductSale
                data = {
                    "sale": sale_instance,
                    "product": product,
                    "quantity": quantity,
                    "price": product.unit_price,
                }
                ProductSale.objects.create(**data)

                # Crear la relación Payment
                data = {
                    "sale": sale_instance,
                    "payment_method": "EF",  # Método de pago por defecto
                    "amount": total,
                }
                Payment.objects.create(**data)

            # Guardar los logs en la base de datos
            StoreProductLog.objects.bulk_create(logs)

            return Response({}, status=status.HTTP_200_OK)

        except ValueError as e:
            print(e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(get_store(), name="dispatch")
class SaleCancelView(APIView):
    def post(self, request):
        sale_id = request.data.get("id")
        sale = get_object_or_404(Sale, id=sale_id)

        if request.data.get("is_canceled"):
            return self._cancel_full(request, sale)
        elif request.data.get("products_to_return"):
            return self._return_partial(request, sale)
        else:
            return Response(
                {"detail": "Se requiere is_canceled o products_to_return."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _cancel_full(self, request, sale):
        logs = []
        with transaction.atomic():
            for ps in sale.products_sale.all():
                sp = StoreProduct.objects.select_for_update().get(
                    store=sale.store, product=ps.product
                )
                previous_stock = sp.stock
                sp.stock += ps.quantity
                sp.save()
                logs.append(StoreProductLog(
                    store_product=sp, user=request.user,
                    previous_stock=previous_stock, updated_stock=sp.stock,
                    action="E", movement="DE",
                ))

            sale.products_sale.all().delete()
            sale.is_canceled = True
            sale.reason_cancel = request.data.get("reason_cancel", "")
            sale.save(update_fields=["is_canceled", "reason_cancel"])
            StoreProductLog.objects.bulk_create(logs)

        return Response(
            {"sale": SaleSerializer(sale).data, "cash_back": sale.total},
            status=status.HTTP_200_OK,
        )

    def _return_partial(self, request, sale):
        products_data = request.data["products_to_return"]
        products_to_return = ProductSale.objects.filter(id__in=products_data.keys())
        if not products_to_return.exists():
            return Response(
                {"detail": "No se encontraron productos."}, status=status.HTTP_404_NOT_FOUND,
            )

        logs = []
        with transaction.atomic():
            for ps in products_to_return:
                qty = products_data.get(str(ps.pk), 0)
                ps.quantity -= qty
                if ps.quantity <= 0:
                    ps.delete()
                else:
                    ps.save()

                sp = StoreProduct.objects.select_for_update().get(
                    store=sale.store, product=ps.product
                )
                previous_stock = sp.stock
                sp.stock += qty
                sp.save()
                logs.append(StoreProductLog(
                    store_product=sp, user=request.user,
                    previous_stock=previous_stock, updated_stock=sp.stock,
                    action="E", movement="DE",
                ))

            new_total = sum(p.get_total() for p in sale.products_sale.all())
            cash_back = sale.total - new_total

            sale.total = new_total
            sale.has_return = True
            sale.reason_return = request.data.get("reason_return", "")
            sale.save(update_fields=["total", "has_return", "reason_return"])
            Payment.objects.filter(sale=sale).update(amount=new_total)
            StoreProductLog.objects.bulk_create(logs)

        return Response(
            {"sale": SaleSerializer(sale).data, "cash_back": cash_back},
            status=status.HTTP_200_OK,
        )
        



@method_decorator(get_store(), name="dispatch")
class SaleDashboardAsyncView(APIView):
    def get(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        tenant = self.request.user.get_tenant()
        stores = Store.objects.filter(tenant=tenant, store_type="T")
        store_ids = list(stores.values_list("id", flat=True))
        
        task = get_sales_for_dashboard.delay(store_ids, year, month)
        
        return Response({"task": task.id})


class CancellationsDashboardView(APIView):
    def get(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month', '0')
        tenant = request.user.get_tenant()
        store_ids = list(Store.objects.filter(tenant=tenant, store_type="T").values_list("id", flat=True))
        task = get_cancellations_dashboard.delay(store_ids, year, month)
        return Response({"task": task.id})


class ProductsDashboardView(APIView):
    def get(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month', '0')
        tenant = request.user.get_tenant()
        store_ids = list(Store.objects.filter(tenant=tenant, store_type="T").values_list("id", flat=True))
        task = get_products_dashboard.delay(tenant.id, store_ids, year, month)
        return Response({"task": task.id})


class StoresCashSummaryView(APIView):
    """
    GET /api/stores-cash-summary/?start_date=...&end_date=...&store_type=T&department_id=...
    Corte de caja bulk: todas las tiendas en ~5 queries.
    Si se envía department_id, filtra por departamento (~2 queries).
    """
    def get(self, request):
        tenant = request.user.get_tenant()
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        store_type = request.GET.get("store_type")
        department_id = request.GET.get("department_id")

        if not start_date or not end_date:
            return Response({"error": "start_date y end_date son requeridos"}, status=status.HTTP_400_BAD_REQUEST)

        if department_id == "0":
            department_id = None

        date_range = [start_date, end_date]
        stores = Store.objects.filter(tenant=tenant).select_related("tenant", "manager").prefetch_related("printer__printer__brand")
        if store_type:
            stores = stores.filter(store_type=store_type)
        store_ids = list(stores.values_list("id", flat=True))
        store_ids_set = set(store_ids)

        if department_id:
            return self._by_department(stores, store_ids, date_range, department_id)
        return self._general(stores, store_ids, store_ids_set, date_range)

    def _by_department(self, stores, store_ids, date_range, department_id):
        # ProductSale filtrado por departamento
        ps_filter = Q(
            sale__store_id__in=store_ids,
            sale__is_canceled=False,
            sale__reservation_in_progress=False,
            sale__created_at__date__range=date_range,
            product__department_id=department_id,
        )

        # 1 — Totales por tienda
        ps_totals = (
            ProductSale.objects.filter(ps_filter)
            .values("sale__store_id")
            .annotate(
                total_received=Sum(F("price") * F("quantity"), output_field=DecimalField()),
                profit=Sum((F("price") - F("product__cost")) * F("quantity"), output_field=DecimalField()),
                sale_count=Count("sale_id", distinct=True),
            )
        )
        ps_map = {r["sale__store_id"]: r for r in ps_totals}

        # 2 — Canceladas por tienda
        canceled = (
            Sale.objects.filter(
                store_id__in=store_ids,
                reservation_in_progress=False,
                is_canceled=True,
                created_at__date__range=date_range,
            )
            .values("store_id")
            .annotate(count=Count("id"))
        )
        canceled_map = {r["store_id"]: r["count"] for r in canceled}

        totals = {"total_payment": 0, "total_sales": 0, "canceled_sales": 0, "profit": 0}
        stores_data = []

        for store in stores:
            sid = store.id
            ps = ps_map.get(sid, {"total_received": 0, "profit": 0, "sale_count": 0})
            total_received = ps["total_received"] or 0
            profit = ps["profit"] or 0
            sale_count = ps["sale_count"] or 0
            canceled_count = canceled_map.get(sid, 0)

            stores_data.append({
                "id": sid,
                "name": store.name,
                "store_type": store.store_type,
                "manager": {"id": store.manager.id, "username": store.manager.username, "full_name": store.manager.get_full_name()} if store.manager else None,
                "cash_summary": {
                    "profit": profit,
                    "total_sales": sale_count,
                    "canceled_sales": canceled_count,
                },
            })

            totals["total_payment"] += total_received
            totals["profit"] += profit
            totals["total_sales"] += sale_count
            totals["canceled_sales"] += canceled_count

        return Response({"stores": stores_data, "totals": totals})

    def _general(self, stores, store_ids, store_ids_set, date_range):

        # Total de productos del tenant
        tenant = stores.first().tenant if stores.exists() else None
        total_products = Product.objects.filter(brand__tenant=tenant).count() if tenant else 0

        # StoreProducts por tienda
        sp_counts = (
            StoreProduct.objects.filter(store_id__in=store_ids)
            .values("store_id")
            .annotate(count=Count("id"))
        )
        sp_count_map = {r["store_id"]: r["count"] for r in sp_counts}

        # 1 — Pagos agrupados por tienda y método
        payments = (
            Payment.objects.filter(
                sale__store_id__in=store_ids,
                sale__is_canceled=False,
                sale__reservation_in_progress=False,
                sale__created_at__date__range=date_range,
            )
            .values("sale__store_id", "payment_method")
            .annotate(total=Sum("amount"))
        )
        payments_map = defaultdict(lambda: {"EF": 0, "TA": 0, "TR": 0})
        for p in payments:
            payments_map[p["sale__store_id"]][p["payment_method"]] = p["total"] or 0

        # 2 — Ganancia por tienda (aggregate en ProductSale)
        profits = (
            ProductSale.objects.filter(
                sale__store_id__in=store_ids,
                sale__is_canceled=False,
                sale__reservation_in_progress=False,
                sale__created_at__date__range=date_range,
            )
            .values("sale__store_id")
            .annotate(
                profit=Sum(
                    (F("price") - F("product__cost")) * F("quantity"),
                    output_field=DecimalField(),
                )
            )
        )
        profit_map = {r["sale__store_id"]: r["profit"] or 0 for r in profits}

        # 3 — Conteo de ventas y canceladas por tienda
        sales_counts = (
            Sale.objects.filter(
                store_id__in=store_ids,
                reservation_in_progress=False,
                created_at__date__range=date_range,
            )
            .values("store_id")
            .annotate(
                total_sales=Count("id", filter=Q(is_canceled=False)),
                canceled_sales=Count("id", filter=Q(is_canceled=True)),
            )
        )
        sales_map = {r["store_id"]: r for r in sales_counts}

        # 4 — CashFlow por tienda
        cashflows = (
            CashFlow.objects.filter(
                store_id__in=store_ids,
                created_at__date__range=date_range,
            )
            .values("store_id", "transaction_type")
            .annotate(total=Sum("amount"))
        )
        cashflow_map = defaultdict(lambda: {"E": 0, "S": 0})
        for cf in cashflows:
            cashflow_map[cf["store_id"]][cf["transaction_type"]] = cf["total"] or 0

        # --- Construir response ---
        totals = {"EF": 0, "TA": 0, "TR": 0, "total_payment": 0, "total_sales": 0, "canceled_sales": 0, "profit": 0, "cash": 0}
        stores_data = []

        for store in stores:
            sid = store.id
            pay = payments_map[sid]
            ef, ta, tr = pay["EF"], pay["TA"], pay["TR"]
            total_payment = ef + ta + tr
            sc = sales_map.get(sid, {"total_sales": 0, "canceled_sales": 0})
            cf = cashflow_map[sid]
            income, expenses = cf["E"], cf["S"]
            net_cashflow = income - expenses
            profit = profit_map.get(sid, 0)
            cash = ef + net_cashflow

            store_printer = store.printer.first()
            stores_data.append({
                "id": sid,
                "name": store.name,
                "full_name": store.get_full_name(),
                "store_type": store.store_type,
                "manager": {"id": store.manager.id, "username": store.manager.username, "full_name": store.manager.get_full_name()} if store.manager else None,
                "has_all_products": sp_count_map.get(sid, 0) >= total_products,
                "printer": {"brand": store_printer.printer.brand.name, "model": store_printer.printer.model} if store_printer else None,
                "cash_summary": {
                    "EF": ef,
                    "TA": ta,
                    "TR": tr,
                    "total_payment": total_payment,
                    "income": income,
                    "expenses": expenses,
                    "net_cashflow": net_cashflow,
                    "cash": cash,
                    "profit": profit,
                    "total_sales": sc["total_sales"],
                    "canceled_sales": sc["canceled_sales"],
                },
            })

            totals["EF"] += ef
            totals["TA"] += ta
            totals["TR"] += tr
            totals["total_payment"] += total_payment
            totals["total_sales"] += sc["total_sales"]
            totals["canceled_sales"] += sc["canceled_sales"]
            totals["profit"] += profit
            totals["cash"] += cash

        return Response({"stores": stores_data, "totals": totals})


@method_decorator(get_store(), name="dispatch")
class DuplicateSalesView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()

        if request.store:
            stores = Store.objects.filter(tenant=tenant, id=request.store.id)
        else:
            stores = Store.objects.filter(tenant=tenant)

        today = timezone.localdate()

        sales = Sale.objects.filter(
            store__in=stores, is_canceled=False, created_at__date=today
        ).select_related("store").order_by("store", "pk")

        duplicates = [s for s in sales.iterator(chunk_size=500) if s.is_repeated()]

        grouped = {}
        for sale in duplicates:
            store_name = sale.store.get_full_name()
            grouped.setdefault(store_name, 0)
            grouped[store_name] += 1

        notifications = [
            {"title": store_name, "messages": [f"{count} venta(s) duplicada(s)"]}
            for store_name, count in grouped.items()
        ]

        return Response(notifications)
