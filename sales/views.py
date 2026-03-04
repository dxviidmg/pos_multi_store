from rest_framework import viewsets
from .serializers import SaleSerializer, SaleCreateSerializer
from .models import Sale, ProductSale, Payment
from products.models import StoreProduct, Product, CashFlow, Store
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
from products.decorators import get_store
from django.utils.decorators import method_decorator
from .cash_summary_utils import calculate_cash_summary
from django.shortcuts import get_object_or_404
from logs.models import StoreProductLog
from rest_framework.exceptions import NotFound
from datetime import datetime
from .tasks import get_sales_for_dashboard

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

        return Sale.objects.filter(**query).select_related(
            "store", "seller", "client"
        ).prefetch_related(
            "products_sale__product__brand",
            "payments"
        ).order_by("-id")

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
class CashSummary(APIView):
    def get(self, request):
        date = request.GET.get("date")
        store = request.store

        response_data = calculate_cash_summary(store, date)

        return Response(response_data)


@method_decorator(get_store(), name="dispatch")
class ImportSalesValidation(APIView):

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
            product_quantities = (
                {}
            )  # Diccionario para rastrear existencias por código de producto

            for _, row in df.iterrows():
                aux = row.to_dict()
                aux["status"] = "Exitoso"

                code = row["code"]
                quantity = row["quantity"]
                try:

                    product = Product.objects.get(code=code, brand__tenant=tenant)
                except Product.DoesNotExist:
                    aux["status"] = "Código no encontrado"
                    data.append(aux)
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
                    aux["status"] = "Cantidad insuficiente"
                    product_quantities[code] = (
                        0  # Actualizar a 0 porque no hay suficiente stock
                    )
                else:
                    product_quantities[code] -= quantity

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
class ImportSales(APIView):

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
class CancelSale(APIView):
    def post(self, request):
        sale_id = request.data.get("id")
        products_data = request.data.get("products_sale_to_cancel")
        reason_cancel = request.data.get("reason_cancel")

        if not sale_id or not products_data:
            return Response(
                {"detail": "Sale ID and products to cancel are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sale = get_object_or_404(Sale, id=sale_id)
        if reason_cancel != "":
            sale.reason_cancel = reason_cancel
            sale.save()

        product_ids = products_data.keys()

        products_to_cancel = ProductSale.objects.filter(id__in=product_ids)
        if not products_to_cancel.exists():
            return Response(
                {"detail": "No products found to cancel."},
                status=status.HTTP_404_NOT_FOUND,
            )

        logs = []
        total_refund = 0

        with transaction.atomic():
            for product_sale in products_to_cancel:

                quantity_to_cancel = products_data.get(str(product_sale.pk), 0)
                product_sale.returned_quantity += quantity_to_cancel
                product_sale.quantity -= quantity_to_cancel
                product_sale.save()

                store_product = StoreProduct.objects.select_for_update().get(
                    store=sale.store, product=product_sale.product
                )

                previous_stock = store_product.stock
                store_product.stock += quantity_to_cancel
                store_product.save()

                logs.append(
                    StoreProductLog(
                        store_product=store_product,
                        user=request.user,
                        previous_stock=previous_stock,
                        updated_stock=store_product.stock,
                        action="E",
                        movement="DE",
                    )
                )

                # Calcular y aplicar reembolso
                if product_sale.quantity == quantity_to_cancel:
                    total_refund += product_sale.get_total()
                else:
                    refund = product_sale.price * quantity_to_cancel
                    total_refund += refund

            # Actualizar o eliminar la venta
            remaining_products = sale.products_sale.all()

            # calcular cash_back de inicio
            cash_back = 0

            if sale.total != sale.get_refunded():
                old_total = sale.total
                new_total = sum(p.get_total() for p in remaining_products)

                sale.total = new_total
                sale.save(update_fields=["total"])

                Payment.objects.filter(sale=sale).update(amount=new_total)

                cash_back = old_total - new_total
            else:
                sale.is_canceled = True
                sale.save(update_fields=["is_canceled"])

                cash_back = sale.total

            StoreProductLog.objects.bulk_create(logs)

            return Response(
                {"sale": SaleSerializer(sale).data, "cash_back": cash_back},
                status=status.HTTP_200_OK,
            )
        



@method_decorator(get_store(), name="dispatch")
class SalesDashboardAsyncView(APIView):
    def get(self, request):
        year = request.query_params.get('year')
        tenant = self.request.user.get_tenant()
        stores = Store.objects.filter(tenant=tenant, store_type="T")
        store_ids = list(stores.values_list("id", flat=True))
        
        task = get_sales_for_dashboard.delay(store_ids, year)
        
        return Response({"task": task.id})