from rest_framework import viewsets
from .serializers import (
    StoreProductSerializer,
    TransferSerializer,
    ProductSerializer,
    BrandSerializer,
    StoreProductBaseSerializer,
    CashFlowSerializer,
    CashFlowCreateSerializer,
    StoreCashSummarySerializer,
    StoreWorkerSerializer,
    DepartmentSerializer,
    StoreProductForStockSerializer,
    StoreBaseSerializer
)
from .models import (
    StoreProduct,
    Product,
    Store,
    Transfer,
    Brand,
    CashFlow,
    StoreWorker,
    Department,
)
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
from django.db import transaction
from products.decorators import get_store
from django.utils.decorators import method_decorator
from datetime import datetime
import pandas as pd
import numpy as np
from django.db.models import Sum
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets
from django.contrib.auth.models import User
from .utils import is_list_in_another, is_positive_number
from logs.models import StoreProductLog

from django.http import JsonResponse
from django.db.models import Sum



@method_decorator(get_store(), name="dispatch")
class StoreProductViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        q = self.request.GET.get("q", "")
        code = self.request.GET.get("code", "")
        only_stock = self.request.GET.get("only_stock", "") == "true"

        if only_stock:
            return StoreProductForStockSerializer
        if not q and not code:
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

        # --- Búsqueda directa por código ---
        if code:
            # Combinar las dos consultas en una sola

            filters = {"product__code": code, "product__brand__tenant": tenant}
            if all_stores == "N":
                filters["store"] = store

            queryset = StoreProduct.objects.filter(**filters).select_related("product")
            
            return queryset.order_by(
                "product__brand__name", "product__name"
            )

        # --- Búsqueda general ---
        product_filters = Q(brand__tenant=tenant)

        if q:
            product_filters &= Q(name__icontains=q) | Q(brand__name__icontains=q)
        if brand_id:
            product_filters &= Q(brand_id=brand_id)
        if department_id:
            product_filters &= Q(department_id=department_id)

        product_queryset = Product.objects.filter(product_filters).select_related(
            "brand"
        )

        if q:
            product_queryset = product_queryset[:200]

        # --- Filtro StoreProduct ---
        storeproduct_filters = Q(product__in=product_queryset)
        if all_stores != "Y":
            storeproduct_filters &= Q(store=store)
        if max_stock:
            storeproduct_filters &= Q(stock__lte=max_stock)

        return (
            StoreProduct.objects.filter(storeproduct_filters)
            .prefetch_related("product")
            .order_by("product__brand__name", "product__name")
        )

    def perform_update(self, serializer):
        instance = (
            serializer.instance
        )  # Instancia del StoreProduct que se está actualizando
        original_stock = (
            instance.stock
        )  # Guardar el stock original antes de la actualización

        serializer.save()  # Guardar los cambios en el objeto

        updated_stock = instance.stock  # Obtener el stock actualizado

        # Registrar un log si el stock cambia
        if original_stock != updated_stock:
            StoreProductLog.objects.create(
                store_product=instance,
                user=self.request.user,
                previous_stock=original_stock,
                updated_stock=updated_stock,
                action="A",
            )


@method_decorator(get_store(), name="dispatch")
class TransferViewSet(viewsets.ModelViewSet):
    serializer_class = TransferSerializer

    def get_queryset(self):
        store = self.request.store

        return Transfer.objects.filter(
            Q(origin_store=store) | Q(destination_store=store), transfer_datetime=None
        ).order_by('-id')

#    def create(self, request, *args, **kwargs):
#        task = create_transfer_task.delay(request.data)
#        return Response(
#            {"task_id": task.id, "status": "processing"},
#            status=status.HTTP_202_ACCEPTED,
#        )


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        brand_id = self.request.GET.get("brand_id")
        department_id = self.request.GET.get("department_id")
        max_stock = self.request.GET.get("max_stock")

        filters = Q(brand__tenant=tenant)

        if brand_id and brand_id != "":
            filters &= Q(brand__id=brand_id)

        if department_id and department_id != "":
            filters &= Q(department__id=department_id)

        queryset = Product.objects.filter(filters).select_related("brand")

        if max_stock:
            queryset = queryset.annotate(
                total_stock=Sum("product_stores__stock")
            ).filter(total_stock__lte=max_stock)

        return queryset.order_by("brand__name", "name")


@method_decorator(get_store(), name="dispatch")
class StoreViewSet(viewsets.ModelViewSet):

    def get_serializer_class(self):
        if self.request.GET.get("start_date"):
            return StoreCashSummarySerializer
        return StoreBaseSerializer
    def get_serializer(self, *args, **kwargs):
        kwargs.setdefault("context", {}).update(
            {"start_date": self.request.GET.get("start_date", None)}
        )
        kwargs.setdefault("context", {}).update(
            {"end_date": self.request.GET.get("end_date", None)}
        )
        kwargs.setdefault("context", {}).update(
            {"department_id": self.request.GET.get("department_id", None)}
        )
        return super().get_serializer(*args, **kwargs)

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        store = self.request.store
        store_type = self.request.GET.get("store_type", None)
        queryset = Store.objects.filter(tenant=tenant)

        if store_type:
            queryset = queryset.filter(store_type=store_type)

        if store:
            queryset = queryset.exclude(id=store.id)

        return queryset


@method_decorator(get_store(), name="dispatch")
class ConfirmProductTransfersView(APIView):
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
                destination_store_product = StoreProduct.objects.get(
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
                        store_related=origin_store
                    )
                )

                # Actualizar el stock en la tienda origen
                origin_store_product = StoreProduct.objects.get(**origin_stock_filter)
                previous_origin_stock = origin_store_product.stock
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
                        store_related=destination_store
                    )
                )

            except StoreProduct.DoesNotExist:
                return Response(
                    {"status": "Product stock not found in one of the stores"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Guardar todos los logs en una sola operación
        StoreProductLog.objects.bulk_create(logs)

        return Response({"status": "Transfer confirmed"}, status=status.HTTP_200_OK)


@method_decorator(get_store(), name="dispatch")
class ConfirmDistributionView(APIView):
    def post(self, request):
        products = request.data.get("products")
        destination_store_id = request.data.get("destination_store")
        origin_store = self.request.store

        if not products or not destination_store_id:
            return Response(
                {"status": "Missing required data"}, status=status.HTTP_400_BAD_REQUEST
            )

        logs = []  # Lista para almacenar los logs de StoreProductLog

        for product_data in products:
            product_id = product_data["product"]["id"]
            quantity = product_data.get("quantity")
            if not product_id or quantity is None or quantity <= 0:
                return Response(
                    {"status": "Id o cantidad invalida"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                # Obtener y actualizar el stock en la tienda destino
                destination_store_product = StoreProduct.objects.get(
                    product=product_id, store=destination_store_id
                )
                previous_dest_stock = destination_store_product.stock
                destination_store_product.stock += quantity
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
                        store_related=origin_store
                    )
                )

                # Obtener y actualizar el stock en la tienda origen
                origin_store_product = StoreProduct.objects.get(
                    product=product_id, store=origin_store.id
                )
                if origin_store_product.stock < quantity:
                    return Response(
                        {"status": f"Insufficient stock for product {product_id}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                previous_origin_stock = origin_store_product.stock
                origin_store_product.stock -= quantity
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
                        store_related=destination_store_product.store
                    )
                )

            except StoreProduct.DoesNotExist:
                return Response(
                    {"status": "Product stock not found in one of the stores"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Guardar todos los logs en una sola operación
        StoreProductLog.objects.bulk_create(logs)

        return Response({"status": "Distribution confirmed"}, status=status.HTTP_200_OK)


class BrandViewSet(viewsets.ModelViewSet):
    serializer_class = BrandSerializer

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        return Brand.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = self.request.user.get_tenant()
        sale_instance = serializer.save(tenant=tenant)
        return sale_instance


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        return Department.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = self.request.user.get_tenant()
        sale_instance = serializer.save(tenant=tenant)
        return sale_instance


@method_decorator(get_store(), name="dispatch")
class AddProductsView(APIView):
    @transaction.atomic
    def post(self, request):
        store_products_data = request.data.get("store_products", [])
        user = request.user

        for store_product_data in store_products_data:
            store_product = StoreProduct.objects.get(id=store_product_data["id"])
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

        store = Store.objects.get(id=pk)

        return Response(
            store.get_investment(),
            status=status.HTTP_200_OK,
        )


class InvestmentsView(APIView):
    def get(self, request):
        user = request.user
        tenant = user.get_tenant()
        stores = Store.objects.filter(tenant=tenant)

        data = [
            {"id": store.id, "investment": store.get_investment()} for store in stores
        ]

        return Response(
            data,
            status=status.HTTP_200_OK,
        )


@method_decorator(get_store(), name="dispatch")
class ProductImportValidationView(APIView):
    def validate_columns(self, df, import_stock):
        expected_columns = [
            "Código",
            "Marca",
            "Departamento",
            "Nombre",
            "Costo",
            "Precio unitario",
            "Precio mayoreo",
            "Cantidad minima mayoreo",
            "Precio Mayoreo en descuento de clientes",
        ]

        if import_stock == "Y":
            expected_columns += ["Cantidad"]

        if not is_list_in_another(expected_columns, list(df.columns)):
            raise ValueError("Formato de excel incorrecto")

    def rename_columns(self, df):
        return df.rename(
            columns={
                "Código": "code",
                "Marca": "brand",
                "Departamento": "departament",
                "Nombre": "name",
                "Costo": "cost",
                "Precio unitario": "unit_price",
                "Precio mayoreo": "wholesale_price",
                "Cantidad minima mayoreo": "min_wholesale_quantity",
                "Precio Mayoreo en descuento de clientes": "wholesale_price_on_client_discount",
                "Cantidad": "quantity",
            }
        )

    def post(self, request):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        create_brands = request.data.get("create_brands")
        create_departments = request.data.get("create_departments")
        departments_mandatory = request.data.get("departments_mandatory")
        import_stock = request.data.get("import_stock")

        tenant = request.user.get_tenant()
        try:
            df = pd.read_excel(file_obj).replace({np.nan: None})
            self.validate_columns(df, import_stock)
            df = self.rename_columns(df)

            if df.empty:
                raise ValueError("El excel esta vacio")

            data, codes = [], dict()

            for _, data_row in enumerate(df.to_dict(orient="records")):
                data_row = {
                    key: value.strip() if isinstance(value, str) else value
                    for key, value in data_row.items()
                }

                data_row["status"] = "Exitoso"
                code = data_row["code"]
                brand = data_row["brand"]
                data_row["excel_row"] = _ + 2

                if not code or code == '':
                    data_row["status"] = "Sin código"
                    data.append(data_row)
                    continue

                if not brand or brand == '':
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
    def validate_columns(self, df, import_stock):
        expected_columns = [
            "Código",
            "Marca",
            "Departamento",
            "Nombre",
            "Costo",
            "Precio unitario",
            "Precio mayoreo",
            "Cantidad minima mayoreo",
            "Precio Mayoreo en descuento de clientes",
        ]

        if import_stock == "Y":
            expected_columns += ["Cantidad"]

        if not is_list_in_another(expected_columns, list(df.columns)):
            raise ValueError("Formato de excel incorrecto")

    def rename_columns(self, df):
        return df.rename(
            columns={
                "Código": "code",
                "Marca": "brand",
                "Nombre": "name",
                "Costo": "cost",
                "Precio unitario": "unit_price",
                "Precio mayoreo": "wholesale_price",
                "Cantidad minima mayoreo": "min_wholesale_quantity",
                "Precio Mayoreo en descuento de clientes": "wholesale_price_on_client_discount",
                "Departamento": "department",
                "Cantidad": "quantity",
            }
        )

    def post(self, request):
        file_obj = request.FILES.get("file")

        if not file_obj:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        tenant = self.request.user.get_tenant()
        import_stock = request.data.get("import_stock")

        try:
            df = pd.read_excel(file_obj).replace({np.nan: None})
            self.validate_columns(df, import_stock)
            df = self.rename_columns(df)

            brand_cache = {}
            department_cache = {}

            logs = []
            for data_row in df.to_dict(orient="records"):

                data_row = {
                    key: value.strip() if isinstance(value, str) else value
                    for key, value in data_row.items()
                }

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
        products = Product.objects.filter(brand__tenant=tenant).filter(Q(code__regex=r"[a-z]") | Q(code__contains="'"))
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
        date = self.request.GET.get("date")
        return CashFlow.objects.filter(store=store, created_at__date=date).order_by('id')

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


class DeleteProductsView(APIView):
    @transaction.atomic
    def post(self, request):
        ids = request.data
        Product.objects.filter(id__in=ids).delete()
        return Response(
            {"status": "success", "message": "Productos borrados correctamente"}
        )


class DeleteBrandsView(APIView):
    @transaction.atomic
    def post(self, request):
        ids = request.data
        Brand.objects.filter(id__in=ids).delete()
        return Response(
            {"status": "success", "message": "Marcas borrados correctamente"}
        )


class DeleteDepartmentsView(APIView):
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

    def validate_columns(self, df):
        expected_columns = ["Código", "Cantidad", "Descripción"]
        if list(df.columns) != expected_columns:
            raise ValueError("Formato de excel incorrecto")

    def rename_columns(self, df):
        return df.rename(
            columns={
                "Código": "code",
                "Cantidad": "quantity",
                "Descripción": "description",
            }
        )

    def post(self, request):
        file_obj = request.FILES.get("file")

        if not file_obj:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        store = self.request.store
        tenant = self.request.user.get_tenant()

        try:
            df = pd.read_excel(file_obj)
            self.validate_columns(df)

            df = self.rename_columns(df)

            all_integers = df["quantity"].apply(lambda x: isinstance(x, int)).all()

            if not all_integers:
                raise ValueError(
                    "No todos los datos en la columna Cantidad son números"
                )

            data = []

            codes = []

            for _, row in df.iterrows():
                aux = row.to_dict()
                aux["status"] = "Exitoso"

                code = row["code"]
                try:

                    product = Product.objects.get(code=code, brand__tenant=tenant)
                    StoreProduct.objects.get(product=product, store=store)
                except Product.DoesNotExist:
                    aux["status"] = "Código no encontrado"
                    data.append(aux)
                    continue
                except StoreProduct.DoesNotExist:
                    aux["status"] = "Producto encontrado pero no existe en la tienda"
                    data.append(aux)
                    continue

                if code in codes:
                    aux["status"] = "Codigo repetido en el archivo"
                else:
                    codes.append(code)

                data.append(aux)

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


@method_decorator(get_store(), name="dispatch")
class ImportStoreProductView(APIView):

    def validate_columns(self, df):
        expected_columns = ["Código", "Cantidad", "Descripción"]
        if list(df.columns) != expected_columns:
            raise ValueError("Formato de excel incorrecto")

    def rename_columns(self, df):
        return df.rename(
            columns={
                "Código": "code",
                "Cantidad": "quantity",
                "Descripción": "description",
            }
        )

    def post(self, request):
        file_obj = request.FILES.get("file")

        if not file_obj:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        tenant = self.request.user.get_tenant()
        store = self.request.store
        seller = self.request.user
        action = request.data.get("action")

        if action not in ["A", "E"]:
            raise ValueError("ERROR EN ACTION")

        try:
            df = pd.read_excel(file_obj)
            self.validate_columns(df)
            df = self.rename_columns(df)

            logs = []  # Lista para almacenar registros de StoreProductLog

            for _, row in df.iterrows():
                code = row["code"]
                quantity = row["quantity"]

                # Obtener el producto y la relación StoreProduct
                product = Product.objects.get(code=code, brand__tenant=tenant)
                store_product = StoreProduct.objects.get(product=product, store=store)

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


class ImportCanIcludeQuantityView(APIView):
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
        store = request.store
        code = request.GET.get("code", "")

        product = Product.objects.select_related("brand").get(code=code, brand__tenant=tenant)
        store_product = StoreProduct.objects.get(store=store, product=product)

        store_type_filter = {} if tenant.displays_stock_in_storages else {"store__store_type": "T"}

        sps = (
            StoreProduct.objects.filter(product=product, **store_type_filter)
            .exclude(id=store_product.id)
            .select_related("store").order_by('-store__store_type', 'store__name')
        )

        data = [
            {
                "store_id": sp.store.id,
                "store_name": sp.store.get_full_name(),
                "available_stock": sp.calculate_available_stock(),
            }
            for sp in sps
        ]

        return Response(data, status=status.HTTP_200_OK)
    

def ping(request):
    return JsonResponse({"status": "alive"})