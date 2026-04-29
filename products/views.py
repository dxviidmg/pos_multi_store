import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import LogAction, LogMovement
from logs.models import ProductPriceLog, StoreProductLog
from notifications.utils import notify_store
from .decorators import get_store
from .import_utils import (
    validate_excel_columns,
    rename_product_columns,
    validate_store_product_columns,
    rename_store_product_columns,
    validate_quantities,
    clean_row_data,
)
from .models import (
    Brand,
    CashFlow,
    Department,
    Distribution,
    Product,
    Store,
    StockUpdateRequest,
    StoreProduct,
    StoreWorker,
    Transfer,
)
from .serializers import (
    BrandSerializer,
    CashFlowCreateSerializer,
    CashFlowSerializer,
    DepartmentSerializer,
    DistributionSerializer,
    ProductSerializer,
    StockUpdateRequestSerializer,
    StoreBaseSerializer,
    StoreCashSummarySerializer,
    StoreProductBaseSerializer,
    StoreProductCodeSerializer,
    StoreProductForStockSerializer,
    StoreProductSerializer,
    StoreWorkerSerializer,
    TransferSerializer,
)
from .utils import is_list_in_another, is_positive_number

# Configuración de límites para archivos Excel
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_ROWS = 10000  # Máximo 10,000 filas
ALLOWED_EXTENSIONS = ['.xlsx', '.xls']
ALLOWED_MIME_TYPES = [
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel'
]


def validate_excel_file(file_obj):
    """Valida tamaño, tipo y formato de archivo Excel"""
    # Validar tamaño
    if file_obj.size > MAX_FILE_SIZE:
        raise ValueError(f"Archivo muy grande. Máximo: {MAX_FILE_SIZE / 1024 / 1024}MB")
    
    # Validar extensión
    import os
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extensión no permitida. Use: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Validar MIME type
    if hasattr(file_obj, 'content_type') and file_obj.content_type not in ALLOWED_MIME_TYPES:
        raise ValueError("Tipo de archivo no válido")
    
    return True


from typing import Optional
from django.db.models import QuerySet


def annotate_stock_info(queryset: QuerySet) -> QuerySet:
    """Agrega anotaciones de stock reservado y disponible al queryset
    
    Args:
        queryset: QuerySet de StoreProduct
        
    Returns:
        QuerySet con anotaciones 'reserved_stock' y 'available_stock'
    """
    from sales.models import ProductSale
    
    # Subquery para stock reservado en transferencias
    reserved_transfers = Transfer.objects.filter(
        product=OuterRef('product'),
        origin_store=OuterRef('store'),
        transfer_datetime__isnull=True,
        distribution__isnull=True
    ).values('product', 'origin_store').annotate(
        total=Sum('quantity')
    ).values('total')
    
    # Subquery para stock reservado en ventas
    reserved_sales = ProductSale.objects.filter(
        product=OuterRef('product'),
        sale__store=OuterRef('store'),
        sale__reservation_in_progress=True
    ).values('product', 'sale__store').annotate(
        total=Sum('quantity')
    ).values('total')
    
    return queryset.annotate(
        reserved_stock=Coalesce(
            Subquery(reserved_transfers, output_field=IntegerField()), 0
        ) + Coalesce(
            Subquery(reserved_sales, output_field=IntegerField()), 0
        ),
        available_stock=F('stock') - F('reserved_stock')
    )

@method_decorator(get_store(), name="dispatch")
class StoreProductViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        q = self.request.GET.get("q", "")
        code = self.request.GET.get("code", "")
        only_stock = self.request.GET.get("only_stock", "") == "true"

        if only_stock:
            return StoreProductForStockSerializer
        if code:
            return StoreProductCodeSerializer
        if not q:
            return StoreProductBaseSerializer
        return StoreProductSerializer

    def get_queryset(self):
        request = self.request
        query_params = request.query_params

        q = query_params.get("q")
        code = query_params.get("code")
        brand_id = query_params.get("brand_id")
        department_id = query_params.get("department_id")
        all_stores = query_params.get("all_stores", "N")
        max_stock = query_params.get("max_stock")

        store = request.store
        tenant = request.user.get_tenant()
        requires_stock_verification = query_params.get("requires_stock_verification") == "true"

        # --- Búsqueda directa por código ---
        if code:
            filters = {"product__code": code, "product__brand__tenant": tenant}
            if all_stores == "N":
                filters["store"] = store
            if requires_stock_verification:
                filters["requires_stock_verification"] = True

            queryset = StoreProduct.objects.filter(**filters).select_related(
                "product", "product__brand", "product__department", "store"
            )
            
            # Agregar anotaciones de stock si es necesario
            if self.get_serializer_class() in (StoreProductSerializer, StoreProductCodeSerializer):
                queryset = annotate_stock_info(queryset)

            return queryset.order_by("product__brand__name", "product__name")

        # --- Búsqueda general ---
        storeproduct_filters = Q(product__brand__tenant=tenant)

        if q:
            storeproduct_filters &= (
                Q(product__name__icontains=q) | Q(product__brand__name__icontains=q)
            )
        if brand_id:
            storeproduct_filters &= Q(product__brand_id=brand_id)
        if department_id:
            storeproduct_filters &= Q(product__department_id=department_id)
        if all_stores != "Y":
            storeproduct_filters &= Q(store=store)
        if max_stock:
            storeproduct_filters &= Q(stock__lte=max_stock)
        if requires_stock_verification:
            storeproduct_filters &= Q(requires_stock_verification=True)

        queryset = StoreProduct.objects.filter(storeproduct_filters).select_related(
            "product", "product__brand", "product__department", "store", "store__tenant", "store__manager"
        ).order_by("product__brand__name", "product__name")

        if q:
            queryset = queryset[:200]
        
        # Agregar anotaciones de stock si es necesario
        if self.get_serializer_class() in (StoreProductSerializer, StoreProductCodeSerializer):
            queryset = annotate_stock_info(queryset)
        
        return queryset

    def perform_update(self, serializer):
        instance = (
            serializer.instance
        )  # Instancia del StoreProduct que se está actualizando
        original_stock = (
            instance.stock
        )  # Guardar el stock original antes de la actualización

        serializer.save()  # Guardar los cambios en el objeto

        updated_stock = instance.stock  # Obtener el stock actualizado

        if instance.requires_stock_verification:
            instance.requires_stock_verification = False
            instance.save(update_fields=['requires_stock_verification'])

        # Registrar un log si el stock cambia y no es igual al último registro
        if original_stock != updated_stock:
            last_log = StoreProductLog.objects.filter(store_product=instance).order_by("-created_at").first()
            if last_log is None or last_log.updated_stock != updated_stock:
                StoreProductLog.objects.create(
                    store_product=instance,
                    user=self.request.user,
                    previous_stock=original_stock,
                    updated_stock=updated_stock,
                    action=LogAction.AJUSTE,
                )


@method_decorator(get_store(), name="dispatch")
class TransferViewSet(viewsets.ModelViewSet):
    serializer_class = TransferSerializer

    def get_queryset(self):
        store = self.request.store
        queryset = Transfer.objects.select_related(
            "origin_store", "destination_store", "product", "product__brand", "distribution"
        ).order_by("-id")

        # Si NO es un GET a detalle (es decir, es listado)
        if self.action == "list":
            queryset = queryset.filter(
                Q(origin_store=store) | Q(destination_store=store),
                transfer_datetime=None,
                distribution=None,
            )

        return queryset

    def perform_create(self, serializer):
        transfer = serializer.save()
        dest = transfer.destination_store
        notify_store(dest, dest.tenant_id, {
            'event': 'transfer_created',
            'message': f'Nuevo traspaso de {transfer.quantity}x {transfer.product.name} desde {transfer.origin_store.name}',
        })

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        brand_id = self.request.GET.get("brand_id")
        department_id = self.request.GET.get("department_id")
        max_stock = self.request.GET.get("max_stock")
        code = self.request.GET.get("code")

        filters = Q(brand__tenant=tenant)

        if brand_id and brand_id != "":
            filters &= Q(brand__id=brand_id)

        if department_id and department_id != "":
            filters &= Q(department__id=department_id)

        if code:
            filters &= Q(code__icontains=code)

        queryset = Product.objects.filter(filters).select_related("brand", "department")

        if max_stock:
            queryset = queryset.annotate(
                total_stock=Sum("product_stores__stock")
            ).filter(total_stock__lte=max_stock)
        
        # Optimizar campos según acción
        if self.action == 'list':
            # Solo campos necesarios para listado
            queryset = queryset.only(
                'id', 'code', 'name', 'unit_price', 'cost',
                'brand__id', 'brand__name',
                'department__id', 'department__name'
            )

        return queryset.order_by("brand__name", "name")

    def perform_update(self, serializer):
        instance = serializer.instance
        tracked_fields = ['cost', 'unit_price', 'wholesale_price', 'min_wholesale_quantity']
        old_values = {f: str(getattr(instance, f)) if getattr(instance, f) is not None else None for f in tracked_fields}
        product = serializer.save()
        logs = []
        for f in tracked_fields:
            new_val = str(getattr(product, f)) if getattr(product, f) is not None else None
            if new_val != old_values[f]:
                logs.append(ProductPriceLog(
                    product=product, user=self.request.user,
                    field=f, previous_value=old_values[f], new_value=new_val,
                ))
        if logs:
            ProductPriceLog.objects.bulk_create(logs)


@method_decorator(get_store(), name="dispatch")
class StoreViewSet(viewsets.ModelViewSet):

    def get_serializer_class(self):
        return StoreBaseSerializer

    def get_serializer(self, *args, **kwargs):
        return super().get_serializer(*args, **kwargs)

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        store = self.request.store
        store_type = self.request.GET.get("store_type", None)
        queryset = Store.objects.filter(tenant=tenant).select_related("tenant", "manager").annotate(
            workers_count=Count("workers")
        )

        if store_type:
            queryset = queryset.filter(store_type=store_type)

        if store:
            queryset = queryset.exclude(id=store.id)

        return queryset


@method_decorator(get_store(), name="dispatch")
class TransferConfirmView(APIView):
    @transaction.atomic  # Decorador para asegurar la atomicidad de todo el método
    def post(self, request):
        transfer_list = request.data.get("transfers")
        destination_store_id = request.data.get("destination_store")
        origin_store = self.request.store

        if not transfer_list or not destination_store_id:
            return Response(
                {"status": "Transfers and destination store are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transfers_to_process = []
        logs = []  # Lista para almacenar los logs de StoreProductLog

        for transfer_item in transfer_list:
            product_id = transfer_item["product"]["id"]
            quantity = transfer_item["quantity"]

            transfer_filter = {
                "product": product_id,
                "quantity": quantity,
                "destination_store": destination_store_id,
                "origin_store": origin_store.id,
                "transfer_datetime": None,
            }

            transfer_record = Transfer.objects.filter(**transfer_filter).first()

            if not transfer_record:
                return Response(
                    {"status": "Transfer not found"}, status=status.HTTP_404_NOT_FOUND
                )

            transfers_to_process.append(
                {"transfer": transfer_record, "quantity": quantity}
            )

        for transfer_info in transfers_to_process:
            transfer = transfer_info["transfer"]

            # Update the transfer timestamp
            transfer.transfer_datetime = datetime.now()
            transfer.save()

            # Update the stock in the destination store
            destination_store = transfer.destination_store

            destination_stock_filter = {
                "product": transfer.product,
                "store": destination_store,
            }
            origin_stock_filter = {
                "product": transfer.product,
                "store": transfer.origin_store,
            }

            try:
                # Actualizar el stock en la tienda destino
                destination_store_product = StoreProduct.objects.select_for_update().get(
                    **destination_stock_filter
                )
                previous_dest_stock = destination_store_product.stock
                destination_store_product.stock += transfer_info["quantity"]
                destination_store_product.save()

                # Log para la tienda destino
                logs.append(
                    StoreProductLog(
                        store_product=destination_store_product,
                        user=request.user,
                        previous_stock=previous_dest_stock,
                        updated_stock=destination_store_product.stock,
                        action="E",  # Acción: Entrada
                        movement="TR",  # Movimiento: Transferencia recibida
                        store_related=origin_store,
                    )
                )

                # Actualizar el stock en la tienda origen
                origin_store_product = StoreProduct.objects.select_for_update().get(**origin_stock_filter)
                previous_origin_stock = origin_store_product.stock
                
                # Validar stock suficiente
                if previous_origin_stock < transfer_info["quantity"]:
                    return Response(
                        {
                            "status": f"Stock insuficiente en tienda origen para {transfer.product.name}. "
                                     f"Disponible: {previous_origin_stock}, Solicitado: {transfer_info['quantity']}"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                
                origin_store_product.stock -= transfer_info["quantity"]
                origin_store_product.save()

                # Log para la tienda origen
                logs.append(
                    StoreProductLog(
                        store_product=origin_store_product,
                        user=request.user,
                        previous_stock=previous_origin_stock,
                        updated_stock=origin_store_product.stock,
                        action="S",  # Acción: Salida
                        movement="TR",  # Movimiento: Transferencia enviada
                        store_related=destination_store,
                    )
                )

            except StoreProduct.DoesNotExist:
                return Response(
                    {"status": "Product stock not found in one of the stores"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Guardar todos los logs en una sola operación
        StoreProductLog.objects.bulk_create(logs)

        notify_store(origin_store, origin_store.tenant_id, {
            'event': 'transfer_confirmed',
            'message': f'Traspaso confirmado hacia tienda destino',
        })

        return Response({"status": "Transfer confirmed"}, status=status.HTTP_200_OK)


#
@method_decorator(get_store(), name="dispatch")
class ConfirmDistributionView(APIView):
    @transaction.atomic
    def post(self, request):
        distribution_id = request.data.get("id")
        distribution = Distribution.objects.get(id=distribution_id)
        transfers = distribution.transfers.all()
        logs = []

        for transfer in transfers:
            destination_store_product = StoreProduct.objects.select_for_update().get(
                product=transfer.product, store=transfer.destination_store
            )
            previous_dest_stock = destination_store_product.stock
            destination_store_product.stock += transfer.quantity
            destination_store_product.save()

            # Log para la tienda destino
            logs.append(
                StoreProductLog(
                    store_product=destination_store_product,
                    user=request.user,
                    previous_stock=previous_dest_stock,
                    updated_stock=destination_store_product.stock,
                    action="E",  # Acción: Entrada
                    movement="DI",  # Movimiento: Distribución recibida
                    store_related=transfer.origin_store,
                )
            )

            # Obtener y actualizar el stock en la tienda origen
            origin_store_product = StoreProduct.objects.select_for_update().get(
                product=transfer.product, store=transfer.origin_store
            )
            previous_origin_stock = origin_store_product.stock
            
            # Validar y ajustar stock si es necesario
            if previous_origin_stock < transfer.quantity:
                origin_store_product.stock = transfer.quantity
                StoreProductLog.objects.create(
                    store_product=origin_store_product,
                    user=request.user,
                    previous_stock=previous_origin_stock,
                    updated_stock=transfer.quantity,
                    action="A",
                    movement="MA"
                )
                origin_store_product.save()
                previous_origin_stock = transfer.quantity

            origin_store_product.stock -= transfer.quantity
            origin_store_product.save()

            # Log para la tienda origen
            logs.append(
                StoreProductLog(
                    store_product=origin_store_product,
                    user=request.user,
                    previous_stock=previous_origin_stock,
                    updated_stock=origin_store_product.stock,
                    action="S",  # Acción: Salida
                    movement="DI",  # Movimiento: Distribución enviada
                    store_related=destination_store_product.store,
                )
            )
            transfer.transfer_datetime = datetime.now()
            transfer.save()

        distribution.transfer_datetime = datetime.now()
        distribution.save()

        # Guardar todos los logs en una sola operación
        StoreProductLog.objects.bulk_create(logs)

        notify_store(distribution.destination_store, distribution.origin_store.tenant_id, {
            'event': 'distribution_confirmed',
            'message': f'Distribución desde {distribution.origin_store.name} confirmada',
        })

        return Response({"status": "Distribution confirmed"}, status=status.HTTP_200_OK)


@method_decorator(get_store(), name="dispatch")
class BrandViewSet(viewsets.ModelViewSet):
    serializer_class = BrandSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['store'] = self.request.store
        context['audit'] = self.request.query_params.get("audit") == "true"
        return context

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        store = self.request.store
        audit = self.request.query_params.get("audit") == "true"
        
        if audit:
            filters = {
                "tenant": tenant,
                "products__product_stores__requires_stock_verification": True
            }
            if store:
                filters["products__product_stores__store"] = store
            queryset = Brand.objects.filter(**filters).distinct().order_by('name')
        else:
            queryset = Brand.objects.filter(tenant=tenant).order_by('name')
        
        if self.action == 'list':
            queryset = queryset.only('id', 'name', 'tenant_id')
        
        return queryset

    def perform_create(self, serializer):
        tenant = self.request.user.get_tenant()
        sale_instance = serializer.save(tenant=tenant)
        return sale_instance


@method_decorator(get_store(), name="dispatch")
class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['store'] = self.request.store
        return context

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        store = self.request.store
        audit = self.request.query_params.get("audit", "") == "true"
        
        if audit:
            filters = {
                "tenant": tenant,
                "products__product_stores__requires_stock_verification": True
            }
            if store:
                filters["products__product_stores__store"] = store
            queryset = Department.objects.filter(**filters).distinct().order_by('name')
        else:
            queryset = Department.objects.filter(tenant=tenant).order_by('name')
        
        if self.action == 'list':
            queryset = queryset.only('id', 'name', 'tenant_id')
        
        return queryset

    def perform_create(self, serializer):
        tenant = self.request.user.get_tenant()
        sale_instance = serializer.save(tenant=tenant)
        return sale_instance


@method_decorator(get_store(), name="dispatch")
class ProductAddView(APIView):
    @transaction.atomic
    def post(self, request):
        store_products_data = request.data.get("store_products", [])
        user = request.user

        for store_product_data in store_products_data:
            store_product = StoreProduct.objects.select_for_update().get(id=store_product_data["id"])
            previous_stock = store_product.stock
            updated_stock = store_product.stock + store_product_data["quantity"]
            store_product.stock = updated_stock
            store_product.save()  # Guardamos el producto actualizado

            # Guardamos el log individualmente
            log = StoreProductLog(
                store_product=store_product,
                user=user,
                previous_stock=previous_stock,
                updated_stock=updated_stock,
                action="E",  # Acción: Entrada
            )
            log.save()

        return Response(
            {"status": "success", "message": "Productos agregados correctamente"}
        )


# @method_decorator(get_store(), name="dispatch")
class StoreInvestmentView(APIView):
    def get(self, request, pk):
        from django.shortcuts import get_object_or_404
        
        user = request.user
        tenant = user.get_tenant()
        store = get_object_or_404(Store, id=pk, tenant=tenant)
        
        return Response(
            store.get_investment(),
            status=status.HTTP_200_OK,
        )


class ResetStoreStockView(APIView):
    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        
        user = request.user
        tenant = user.get_tenant()
        store = get_object_or_404(Store, id=pk, tenant=tenant)
        
        store.store_products.update(stock=0)
        
        return Response(status=status.HTTP_200_OK)


@method_decorator(get_store(), name="dispatch")
class ProductImportValidationView(APIView):
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

        create_brands = request.data.get("create_brands")
        create_departments = request.data.get("create_departments")
        departments_mandatory = request.data.get("departments_mandatory")
        import_stock = request.data.get("import_stock")

        tenant = request.user.get_tenant()
        try:
            df = pd.read_excel(file_obj, nrows=MAX_ROWS).replace({np.nan: None})
            
            if len(df) > MAX_ROWS:
                return Response(
                    {"error": f"Demasiadas filas. Máximo: {MAX_ROWS}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            validate_excel_columns(df, import_stock)
            df = rename_product_columns(df)

            if df.empty:
                raise ValueError("El excel esta vacio")

            data, codes = [], dict()

            for _, data_row in enumerate(df.to_dict(orient="records")):
                data_row = clean_row_data(data_row)

                data_row["status"] = "Exitoso"
                code = data_row["code"]
                brand = data_row["brand"]
                data_row["excel_row"] = _ + 2

                if not code or code == "":
                    data_row["status"] = "Sin código"
                    data.append(data_row)
                    continue

                if not brand or brand == "":
                    data_row["status"] = "Sin marca"
                    data.append(data_row)
                    continue

                if Product.objects.filter(code=code, brand__tenant=tenant).exists():
                    data_row["status"] = "Código existente en el sistema"
                elif code in codes:
                    data_row["status"] = "Código existente en la fila " + str(
                        codes[code]
                    )
                else:
                    codes[code] = data_row["excel_row"]

                    v1, v2 = data_row.get("wholesale_price"), data_row.get(
                        "min_wholesale_quantity"
                    )
                    if (v1 is None) ^ (v2 is None):
                        data_row["status"] = (
                            "Si existe mayoreo debe ingresar el precio mayoreo y la cantidad mínima"
                        )
                    else:
                        prices = [data_row.get("cost"), data_row.get("unit_price")]
                        if v1 is not None and v2 is not None:
                            prices.extend([v1, v2])

                        try:
                            prices = [
                                float(price) for price in prices if price is not None
                            ]
                            if not all(price > 0 for price in prices):
                                data_row["status"] = (
                                    "Costo y precio(s) deben ser mayores a 0"
                                )

                            if len(prices) == 4 and prices[2] > prices[1]:
                                data_row["status"] = (
                                    "Precio mayoreo es mas grande que precio unitario"
                                )

                            if len(prices) == 4 and prices[0] > prices[2]:
                                data_row["status"] = (
                                    "Precio mayoreo es mas chico que costo"
                                )

                        except ValueError:
                            data_row["status"] = "Precios o costos inválidos"

                    if create_brands == "N":
                        try:
                            Brand.objects.get(name=data_row["brand"])
                        except Brand.DoesNotExist:
                            data_row["status"] = "Marca inexistente"

                    if create_departments == "N":
                        try:
                            Department.objects.get(name=data_row["departament"])
                        except Department.DoesNotExist:
                            if departments_mandatory == "Y":
                                data_row["status"] = "Departamento inexistente"

                    if import_stock == "Y":
                        is_positivo = is_positive_number(data_row["quantity"])

                        if not is_positivo:
                            data_row["status"] = "Cantidad debe ser un número positivo"

                data.append(data_row)

            return Response(data, status=status.HTTP_200_OK)

        except ValueError as e:
            print(e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProductImport(APIView):
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
        import_stock = request.data.get("import_stock")

        try:
            df = pd.read_excel(file_obj, nrows=MAX_ROWS).replace({np.nan: None})
            
            if len(df) > MAX_ROWS:
                return Response(
                    {"error": f"Demasiadas filas. Máximo: {MAX_ROWS}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            validate_excel_columns(df, import_stock)
            df = rename_product_columns(df)

            brand_cache = {}
            department_cache = {}

            logs = []
            for data_row in df.to_dict(orient="records"):

                data_row = clean_row_data(data_row)

                quantity = data_row.pop("quantity")
                brand_name = data_row["brand"]
                if brand_name not in brand_cache:
                    brand_cache[brand_name], _ = Brand.objects.get_or_create(
                        name=brand_name, tenant=tenant
                    )

                data_row["brand"] = brand_cache[brand_name]

                department_name = data_row["department"]

                if department_name:
                    data_row["department"] = department_cache.get(
                        department_name,
                        Department.objects.get_or_create(
                            name=department_name, tenant=tenant
                        )[0],
                    )
                else:
                    data_row["department"] = None

                data_row["wholesale_price_on_client_discount"] = bool(
                    data_row["wholesale_price_on_client_discount"]
                )

                data_row["brand"] = brand_cache[brand_name]
                data_row["wholesale_price_on_client_discount"] = bool(
                    data_row["wholesale_price_on_client_discount"]
                )

                if len(data_row["name"]) > 100:
                    data_row["name"] = data_row["name"][:100]

                code_exists = Product.objects.filter(
                    code=data_row["code"], brand__tenant=tenant
                ).exists()
                if code_exists:
                    continue

                product = Product(**data_row)
                product.save()  # D

                if import_stock == "Y":
                    updated_stock = quantity
                    store = Store.objects.get(tenant=tenant)
                    sp = StoreProduct.objects.get(store=store, product=product)
                    previous_stock = sp.stock
                    sp.stock = quantity
                    sp.save()

                    logs.append(
                        StoreProductLog(
                            store_product=sp,
                            user=request.user,
                            previous_stock=previous_stock,
                            updated_stock=updated_stock,
                            action="A",
                            movement="IM",  # Movimiento: Venta
                        )
                    )

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


class ProductReassignView(APIView):
    def post(self, request):
        reassign_type = request.data.get("reassign_type")
        origin_id = request.data.get("origin_id")
        destination_id = request.data.get("destination_id")
        delete_origin = request.data.get("delete_origin") == "true"

        filter = {reassign_type: origin_id}
        update_data = {reassign_type: destination_id}
        Product.objects.filter(**filter).update(**update_data)

        if delete_origin:
            if reassign_type == "brand":
                origin = Brand.objects.get(id=origin_id)
            else:
                origin = Department.objects.get(id=origin_id)
            origin.delete()

        return Response({}, status=status.HTTP_200_OK)


class ProductUpperCodeView(APIView):
    def post(self, request):
        tenant = self.request.user.get_tenant()
        products = Product.objects.filter(brand__tenant=tenant).filter(
            Q(code__regex=r"[a-z]") | Q(code__contains="'")
        )
        products_to_update = []
        for product in products:
            product.code = product.code.upper().replace("'", "-")
            products_to_update.append(product)

        Product.objects.bulk_update(products_to_update, ["code"])

        return Response({"productos": len(products)}, status=status.HTTP_200_OK)


@method_decorator(get_store(), name="dispatch")
class CashFlowViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.method == "POST":
            return CashFlowCreateSerializer
        return CashFlowSerializer

    def get_queryset(self):
        store = self.request.store
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        return CashFlow.objects.filter(store=store, created_at__date__range=(start_date, end_date)).order_by(
            "id"
        )

    @action(detail=False, methods=["get"])
    def choices(self, request):
        choices = [
            {"value": key, "label": label}
            for key, label in CashFlow.TRANSACTION_TYPES_CHOICES
        ]
        return Response(choices)

    def perform_create(self, serializer):
        store = self.request.store
        sale_instance = serializer.save(store=store, user=self.request.user)
        return sale_instance


class ProductDeleteView(APIView):
    @transaction.atomic
    def post(self, request):
        ids = request.data
        Product.objects.filter(id__in=ids).delete()
        return Response(
            {"status": "success", "message": "Productos borrados correctamente"}
        )


class BrandDeleteView(APIView):
    @transaction.atomic
    def post(self, request):
        ids = request.data
        Brand.objects.filter(id__in=ids).delete()
        return Response(
            {"status": "success", "message": "Marcas borrados correctamente"}
        )


class DepartmentDeleteView(APIView):
    @transaction.atomic
    def post(self, request):
        ids = request.data
        Department.objects.filter(id__in=ids).delete()
        return Response(
            {"status": "success", "message": "Marcas borrados correctamente"}
        )


@method_decorator(get_store(), name="dispatch")
class StoreWorkerViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        return StoreWorkerSerializer

    def get_serializer(self, *args, **kwargs):
        kwargs.setdefault("context", {}).update(
            {"start_date": self.request.GET.get("start_date", None)}
        )
        kwargs.setdefault("context", {}).update(
            {"end_date": self.request.GET.get("end_date", None)}
        )
        return super().get_serializer(*args, **kwargs)

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        return StoreWorker.objects.filter(store__tenant=tenant)

    def perform_create(self, serializer):
        worker_data = self.request.data.pop("worker")
        worker = User.objects.create(**worker_data)
        worker.set_password(worker_data["username"])  # Encripta la contraseña
        worker.save()

        store = Store.objects.get(id=self.request.data["store_id"])
        store_worker = StoreWorker.objects.create(worker=worker, store=store)
        serializer = StoreWorkerSerializer(data=store_worker)
        if serializer.is_valid():
            store_worker = serializer.save()
            return Response(
                StoreWorkerSerializer(store_worker).data, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(get_store(), name="dispatch")
class StoreProductImportValidationView(APIView):
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

            codes = []

            for _, row in df.iterrows():
                row_data = row.to_dict()
                row_data["status"] = "Exitoso"

                code = row["code"]
                try:

                    product = Product.objects.get(code=code, brand__tenant=tenant)
                    StoreProduct.objects.get(product=product, store=store)
                except Product.DoesNotExist:
                    row_data["status"] = "Código no encontrado"
                    validation_results.append(row_data)
                    continue
                except StoreProduct.DoesNotExist:
                    row_data["status"] = "Producto encontrado pero no existe en la tienda"
                    validation_results.append(row_data)
                    continue

                if code in codes:
                    row_data["status"] = "Codigo repetido en el archivo"
                else:
                    codes.append(code)

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
class ImportStoreProductView(APIView):
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
        action = request.data.get("action")

        if action not in ["A", "E"]:
            raise ValueError("ERROR EN ACTION")

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
                updated_stock = previous_stock + quantity if action == "E" else quantity

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
                        action=action,
                        movement="IM",  # Movimiento: Venta
                    )
                )

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


class StoreProductCanIncludeQuantityView(APIView):
    def get(self, request):
        tenant = self.request.user.get_tenant()
        store_count = Store.objects.filter(tenant=tenant).count()
        if store_count == 1:
            return Response(True, status=status.HTTP_200_OK)
        return Response(False, status=status.HTTP_200_OK)


@method_decorator(get_store(), name="dispatch")
class StockInOtherStores(APIView):
    def get(self, request):
        user = request.user
        tenant = user.get_tenant()
        store_product_id = request.GET.get("store-product", "")

        store_product = StoreProduct.objects.select_related("store", "product").get(
            id=store_product_id, store__tenant=tenant
        )
        product = store_product.product

        store_type_filter = (
            {} if tenant.displays_stock_in_storages else {"store__store_type": "T"}
        )

        sps = (
            StoreProduct.objects.filter(product=product, **store_type_filter)
            .exclude(id=store_product.id)
            .select_related("store")
            .order_by("-store__store_type", "store__name")
        )
        
        # Agregar anotaciones de stock
        sps = annotate_stock_info(sps)

        stock_data = [
            {
                "store_id": sp.store.id,
                "store_name": sp.store.get_full_name(),
                "available_stock": sp.available_stock,
            }
            for sp in sps
        ]

        return Response(stock_data, status=status.HTTP_200_OK)


def ping(request):
    return JsonResponse({"status": "alive"})


@method_decorator(get_store(), name="dispatch")
class PendingMovementsView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()

        if request.store:
            stores = Store.objects.filter(tenant=tenant, id=request.store.id)
        else:
            stores = Store.objects.filter(tenant=tenant)

        pending_transfers = Transfer.objects.filter(
            Q(origin_store__in=stores) | Q(destination_store__in=stores),
            transfer_datetime__isnull=True, distribution__isnull=True
        ).select_related('origin_store', 'destination_store')

        pending_distributions = Distribution.objects.filter(
            Q(origin_store__in=stores) | Q(destination_store__in=stores),
            transfer_datetime__isnull=True
        ).select_related('origin_store', 'destination_store')

        grouped = {}

        for t in pending_transfers:
            key = (t.origin_store.name, t.destination_store.name)
            grouped.setdefault(key, {"transfers": 0, "distributions": 0})
            grouped[key]["transfers"] += 1

        for d in pending_distributions:
            key = (d.origin_store.name, d.destination_store.name)
            grouped.setdefault(key, {"transfers": 0, "distributions": 0})
            grouped[key]["distributions"] += 1

        notifications = []
        for (origin, dest), counts in grouped.items():
            messages = []
            if counts["distributions"]:
                messages.append(f"{counts['distributions']} distribución(es)")
            if counts["transfers"]:
                messages.append(f"{counts['transfers']} traspaso(s)")
            notifications.append({"title": f"{origin} → {dest}", "messages": messages})

        # Solicitudes de ajuste de stock en el último minuto
        one_minute_ago = timezone.now() - timedelta(minutes=1)
        recent_requests = StockUpdateRequest.objects.filter(
            store_product__store__in=stores, applied=False,
            created_at__gte=one_minute_ago,
        ).select_related('store_product__store', 'store_product__product', 'requested_by')

        for req in recent_requests:
            notifications.append({
                "title": req.store_product.store.name,
                "messages": [f"Solicitud de ajuste: {req.store_product.product.name} ({req.requested_by.first_name})"],
            })

        return Response(notifications)


@method_decorator(get_store(), name="dispatch")
class DistributionViewSet(viewsets.ModelViewSet):
    serializer_class = DistributionSerializer

    def get_queryset(self):
        store = self.request.store

        return Distribution.objects.filter(
            Q(origin_store=store) | Q(destination_store=store), transfer_datetime=None
        ).select_related("origin_store", "destination_store").prefetch_related(
            "transfers__product__brand"
        ).order_by("-id")

    def perform_create(self, serializer):
        origin_store = self.request.store
        distribution_instance = serializer.save(origin_store=origin_store)

        products = self.request.data.get("products")
        destination_store_id = self.request.data.get("destination_store")

        if not products or not destination_store_id:
            return Response(
                {"status": "Missing required data"}, status=status.HTTP_400_BAD_REQUEST
            )

        #        destination_store = Store.objects.get(id=destination_store_id)
        for product_data in products:
            product_id = product_data["product"]["id"]
            quantity = product_data.get("quantity")
            if not product_id or quantity is None or quantity <= 0:
                return Response(
                    {"status": "Id o cantidad invalida"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                data_transfer = {
                    "distribution": distribution_instance,
                    "origin_store": origin_store,
                    "destination_store_id": destination_store_id,
                    "product_id": product_id,
                    "quantity": quantity,
                }
                Transfer.objects.create(**data_transfer)

            except StoreProduct.DoesNotExist:
                return Response(
                    {"status": "Product stock not found in one of the stores"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        dest = distribution_instance.destination_store
        notify_store(dest, dest.tenant_id, {
            'event': 'distribution_created',
            'message': f'Nueva distribución desde {origin_store.name}',
        })

        return distribution_instance


class StockUpdateRequestViewSet(viewsets.ModelViewSet):
    serializer_class = StockUpdateRequestSerializer
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        return (
            StockUpdateRequest.objects
            .filter(store_product__store__tenant=tenant, applied=False)
            .select_related('requested_by', 'store_product__product__brand', 'store_product__store')
            .order_by('-created_at')
        )

    def perform_create(self, serializer):
        sp = serializer.validated_data['store_product']
        if StockUpdateRequest.objects.filter(store_product=sp, applied=False).exists():
            raise ValidationError({"error": "Ya hay una solicitud en proceso para este producto-tienda"})
        instance = serializer.save(requested_by=self.request.user)
        store = sp.store
        notify_store(store, store.tenant_id, {
            'event': 'stock_request_created',
            'message': f'Solicitud de ajuste de stock para {sp.product.name} en {store.name}',
        })

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        adj = self.get_object()
        if adj.applied:
            return Response({"error": "Ya fue aplicada"}, status=status.HTTP_400_BAD_REQUEST)

        sp = adj.store_product
        previous_stock = sp.stock
        sp.stock = adj.requested_stock
        sp.requires_stock_verification = False
        sp.save()
        adj.applied = True
        adj.save()

        StoreProductLog.objects.create(
            store_product=sp, user=request.user,
            previous_stock=previous_stock, updated_stock=adj.requested_stock,
            action=LogAction.AJUSTE, movement=LogMovement.MANUAL,
        )
        store = sp.store
        notify_store(store, store.tenant_id, {
            'event': 'stock_request_approved',
            'message': f'Ajuste de stock aprobado para {sp.product.name} en {store.name}',
        })
        return Response(StockUpdateRequestSerializer(adj).data)


class StockVerificationDashboardView(APIView):
    def get(self, request):
        from .tasks import get_stock_verification_dashboard
        tenant = request.user.get_tenant()
        store_ids = list(Store.objects.filter(tenant=tenant, store_type="T").values_list("id", flat=True))
        task = get_stock_verification_dashboard.delay(store_ids)
        return Response({"task": task.id})
