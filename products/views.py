from rest_framework import viewsets
from .serializers import (
    StoreProductSerializer,
    TransferSerializer,
    StoreSerializer,
    ProductSerializer,
    BrandSerializer,
    StoreProductBaseSerializer,
    StoreProductLogSerializer,
)
from .models import StoreProduct, Product, Store, Transfer, Brand, StoreProductLog
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


@method_decorator(get_store(), name="dispatch")
class StoreProductViewSet(viewsets.ModelViewSet):
    serializer_class = StoreProductSerializer
    alternate_serializer_class = StoreProductBaseSerializer

    def get_serializer_class(self):
        q = self.request.GET.get("q", "")
        code = self.request.GET.get("code", "")

        if not q and not code:
            return StoreProductBaseSerializer

        return StoreProductSerializer

    def get_queryset(self):
        q = self.request.GET.get("q", None)
        code = self.request.GET.get("code", None)

        # Intentar obtener la tienda, retornar un queryset vacío si no existe
        store = self.request.store
        tenant = self.request.user.get_tenant()

        # Filtrar por código del producto si está especificado
        if code:
            product = Product.objects.filter(code=code, brand__tenant=tenant).first()
            return (
                StoreProduct.objects.filter(product=product, store=store)
                if product
                else []
            )

        # Construir la consulta de búsqueda en `Product` si se proporciona `q`

        if q:
            filters = Q()

            filters |= (
                Q(brand__name__icontains=q)
                | Q(code__icontains=q)
                | Q(name__icontains=q)
            )

            # Obtener productos y filtrar `StoreProduct` según la tienda
            product_queryset = Product.objects.filter(
                filters, brand__tenant=tenant
            ).select_related("brand")[:50]
        else:
            brands = Brand.objects.filter(tenant=tenant)
            product_queryset = Product.objects.filter(brand__in=brands).select_related(
                "brand"
            )

        return StoreProduct.objects.filter(
            product__in=product_queryset, store=store
        ).prefetch_related("product")

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
        )


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        return Product.objects.filter(brand__tenant=tenant)


@method_decorator(get_store(), name="dispatch")
class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = StoreSerializer

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        store = self.request.store

        if store:
            return Store.objects.filter(store_type="T", tenant=tenant).exclude(
                id=store.id
            )
        return Store.objects.filter(tenant=tenant)


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
            product_id = transfer_item["product_id"]
            quantity = transfer_item["quantity"]

            transfer_filter = {
                "product": product_id,
                "quantity": quantity,
                "destination_store": destination_store_id,
                "origin_store": origin_store.id,
                "transfer_datetime": None,
            }

            try:
                transfer_record = Transfer.objects.get(**transfer_filter)
            except Transfer.DoesNotExist:
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
    @transaction.atomic  # Decorador para asegurar la atomicidad de todo el método
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
            product_id = product_data.get("product_id")
            quantity = product_data.get("quantity")

            if not product_id or quantity is None or quantity <= 0:
                return Response(
                    {"status": "Invalid product data"},
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


@method_decorator(get_store(), name="dispatch")
class AddProductsView(APIView):
    @transaction.atomic
    def post(self, request):
        product_list = request.data.get("products")
        store = self.request.store
        user = request.user  # Asumiendo que el usuario está autenticado

        product_ids = [product_data["product_id"] for product_data in product_list]
        store_products = StoreProduct.objects.filter(
            product__in=product_ids, store=store
        )

        store_product_dict = {
            store_product.product_id: store_product for store_product in store_products
        }

        logs = []  # Lista para almacenar los logs

        for product_data in product_list:
            product_id = product_data["product_id"]
            if product_id in store_product_dict:
                store_product = store_product_dict[product_id]
                previous_stock = store_product.stock
                updated_stock = previous_stock + product_data["quantity"]

                # Actualizar el stock del producto
                store_product.stock = updated_stock

                # Crear el log correspondiente
                logs.append(
                    StoreProductLog(
                        store_product=store_product,
                        user=user,
                        previous_stock=previous_stock,
                        updated_stock=updated_stock,
                        action="E",  # Acción: Entrada
                    )
                )

        # Guardar los productos actualizados en la base de datos
        StoreProduct.objects.bulk_update(store_products, ["stock"])

        # Guardar los logs en la base de datos
        StoreProductLog.objects.bulk_create(logs)

        return Response(
            {"status": "success", "message": "Productos agregados correctamente"}
        )


@method_decorator(get_store(), name="dispatch")
class StoreProductLogsView(APIView):
    @transaction.atomic  # Decorador para asegurar la atomicidad de todo el método
    def get(self, request, pk):
        store_product_logs = StoreProductLog.objects.filter(
            store_product__id=pk
        ).order_by("-id")
        serializer = StoreProductLogSerializer(store_product_logs, many=True)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# @method_decorator(get_store(), name="dispatch")
class StoreInvestmentView(APIView):
    def get(self, request, pk):
        store_products = StoreProduct.objects.filter(store__id=pk)

        store_investment = 0
        for store_product in store_products:
            if store_product.stock == 0:
                continue

            store_investment_by_product = (
                store_product.stock * store_product.product.cost
            )

            store_investment += store_investment_by_product
        return Response(
            store_investment,
            status=status.HTTP_200_OK,
        )


@method_decorator(get_store(), name="dispatch")
class ProductImportValidation(APIView):
    def validate_columns(self, df):
        expected_columns = [
            "Código",
            "Marca",
            "Nombre",
            "Costo",
            "Precio unitario",
            "Precio mayoreo",
            "Cantidad minima mayoreo",
            "Precio Mayoreo en descuento de clientes",
        ]
        if list(df.columns) != expected_columns:
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
            }
        )

    def post(self, request):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        tenant = request.user.get_tenant()
        try:
            df = pd.read_excel(file_obj).replace({np.nan: None})
            self.validate_columns(df)
            df = self.rename_columns(df)
            
            data, codes = [], set()
            
            for _, row in df.iterrows():
                aux = row.to_dict()
                aux["status"] = "Exitoso"
                code = row["code"]
                
                if Product.objects.filter(code=code, brand__tenant=tenant).exists():
                    aux["status"] = "Código encontrado"
                elif code in codes:
                    aux["status"] = "Código añadido en el archivo"
                else:
                    codes.add(code)
                    
                    v1, v2 = aux.get("wholesale_price"), aux.get("min_wholesale_quantity")
                    if (v1 is None) ^ (v2 is None):
                        aux["status"] = "Si existe mayoreo debe ingresar el precio mayoreo y la cantidad mínima"
                    else:
                        prices = [aux.get("cost"), aux.get("unit_price")]
                        if v1 is not None and v2 is not None:
                            prices.extend([v1, v2])
                        
                        try:
                            prices = [float(price) for price in prices if price is not None]
                            if not all(price > 0 for price in prices):
                                aux["status"] = "Al menos uno de los valores no es mayor a 0"
                        except ValueError:
                            aux["status"] = "Valores inválidos"
                
                data.append(aux)
            
            return Response(data, status=status.HTTP_200_OK)
        
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class ProductImport(APIView):

    def validate_columns(self, df):
        expected_columns = [
            "Código",
            "Marca",
            "Nombre",
            "Costo",
            "Precio unitario",
            "Precio mayoreo",
            "Cantidad minima mayoreo",
            "Precio Mayoreo en descuento de clientes",
        ]
        if list(df.columns) != expected_columns:
            raise ValueError("Formato de excel incorrecto")
        if list(df.columns) != expected_columns:
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
            }
        )

    def post(self, request):
        file_obj = request.FILES.get("file")

        if not file_obj:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        tenant = self.request.user.get_tenant()

        try:
            df = pd.read_excel(file_obj).replace({np.nan: None})
            self.validate_columns(df)
            df = self.rename_columns(df)


            brand_cache = {}

            products = []
            for data_row in df.to_dict(orient='records'):
                brand_name = data_row['brand']
                if brand_name not in brand_cache:
                    brand_cache[brand_name], _ = Brand.objects.get_or_create(name=brand_name, tenant=tenant)
                
                data_row['brand'] = brand_cache[brand_name]
                data_row['wholesale_price_on_client_discount'] = bool(data_row['wholesale_price_on_client_discount'])

                products.append(Product(**data_row))

            Product.objects.bulk_create(products)




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
