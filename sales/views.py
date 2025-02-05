from rest_framework import viewsets
from .serializers import SaleSerializer, SaleCreateSerializer
from .models import Sale, ProductSale, Payment
from products.models import StoreProduct, Product, StoreProductLog, Printer
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum
import pandas as pd
from products.decorators import get_store
from django.utils.decorators import method_decorator


@method_decorator(get_store(), name="dispatch")
# Create your views here.
class SaleViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.method == "POST":
            return SaleCreateSerializer
        return SaleSerializer

    def get_queryset(self):
        date = self.request.GET.get("date")
        store = self.request.store
        return Sale.objects.filter(store=store, created_at__date=date)
    def perform_create(self, serializer):
        store_products_data = self.request.data.get("store_products")
        payments_data = self.request.data.get("payments")

        if not store_products_data or not payments_data:
            return Response(
                {"detail": "store_products and payments are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_store_products = []  # Lista para almacenar instancias de StoreProduct
        logs = []  # Lista para almacenar logs de StoreProductLog

        store = self.request.store
        saler = self.request.user

        # Usar una transacción para asegurar la atomicidad
        with transaction.atomic():
            for product_data in store_products_data:
                product_store = StoreProduct.objects.get(id=product_data["id"])
                previous_stock = product_store.stock
                updated_stock = previous_stock - product_data["quantity"]

                # Actualizar el stock del producto
                product_store.stock = updated_stock
                updated_store_products.append(product_store)

                # Crear el log correspondiente
                logs.append(
                    StoreProductLog(
                        store_product=product_store,
                        user=saler,
                        previous_stock=previous_stock,
                        updated_stock=updated_stock,
                        action="S",  # Acción: Salida
                        movement="VE",  # Movimiento: Venta
                    )
                )

            # Actualizar los stocks de los productos en una sola operación
            StoreProduct.objects.bulk_update(updated_store_products, ["stock"])

            # Guardar los logs en la base de datos
            StoreProductLog.objects.bulk_create(logs)

            # Guardar la venta y asociarla al usuario actual
            sale_instance = serializer.save(store=store, saler=saler)

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
                }
                Payment.objects.create(**data)

        return sale_instance


@method_decorator(get_store(), name="dispatch")
class DailyEarnings(APIView):
    def get(self, request):
        date = request.GET.get("date")
        store = request.store
        user_sales = Sale.objects.filter(store=store, created_at__date=date)
        total_sales_sum = user_sales.aggregate(total=Sum("total"))["total"] or 0
        related_payments = Payment.objects.filter(sale__in=user_sales)
        payments_by_method = related_payments.values("payment_method").annotate(
            total_amount=Sum("amount")
        )
        total_payments_sum = (
            related_payments.aggregate(total=Sum("amount"))["total"] or 0
        )

        # Obtener significados de métodos de pago
        payment_methods_meaning = dict(Payment.PAYMENT_METHOD_CHOICES)
        payments_by_method = [
            {
                "payment_method": payment_methods_meaning.get(
                    payment["payment_method"], payment["payment_method"]
                ),
                "total_amount": payment["total_amount"],
            }
            for payment in payments_by_method
        ]

        payments_by_method.extend(
            [
                {"payment_method": "Total en ventas", "total_amount": total_sales_sum},
                {
                    "payment_method": "Total en pagos",
                    "total_amount": total_payments_sum,
                },
                {
                    "payment_method": "Balanceado",
                    "total_amount": (
                        "Si" if total_sales_sum == total_payments_sum else "No"
                    ),
                },
            ]
        )

        return Response(payments_by_method)


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
        saler = self.request.user

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
                        user=saler,
                        previous_stock=previous_stock,
                        updated_stock=updated_stock,
                        action="S",  # Acción: Salida
                        movement="VE",  # Movimiento: Venta
                    )
                )

                # Calcular el total de la venta y registrar la venta
                total = product.unit_price * quantity
                sale_instance = Sale.objects.create(
                    store=store, total=total, saler=saler
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
        products_sale_to_cancel_ids = request.data.get("products_sale_to_cancel")

        if not sale_id or not products_sale_to_cancel_ids:
            return Response(
                {"detail": "Sale ID and products to cancel are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sale = Sale.objects.get(id=sale_id)
        except Sale.DoesNotExist:
            return Response(
                {"detail": "No sale found to cancel."},
                status=status.HTTP_404_NOT_FOUND,
            )

        products_sale_to_cancel = ProductSale.objects.filter(
            id__in=products_sale_to_cancel_ids
        )

        if not products_sale_to_cancel.exists():
            return Response(
                {"detail": "No products found to cancel."},
                status=status.HTTP_404_NOT_FOUND,
            )

        cash_back = 0
        logs = []  # Lista para almacenar registros de StoreProductLog

        # Use a transaction to ensure atomicity
        with transaction.atomic():
            for product_sale in products_sale_to_cancel:
                store_product = StoreProduct.objects.filter(
                    store=sale.store, product=product_sale.product
                ).first()

                if store_product:
                    previous_stock = store_product.stock
                    updated_stock = previous_stock + product_sale.quantity

                    # Actualizar el stock del producto
                    store_product.stock = updated_stock
                    store_product.save()

                    # Crear un log para esta operación
                    logs.append(
                        StoreProductLog(
                            store_product=store_product,
                            user=request.user,
                            previous_stock=previous_stock,
                            updated_stock=updated_stock,
                            action="E",  # Acción: Entrada
                            movement="DE",  # Movimiento: Cancelación de compra
                        )
                    )

                cash_back += product_sale.get_total()
                product_sale.delete()

            # Recalculate the sale total
            remaining_products = sale.products_sale.all()
            if remaining_products.exists():
                total = sum(
                    product.get_total() for product in remaining_products
                )
                sale.total = total
                sale.save()

                payment = Payment.objects.get(sale=sale)
                payment.amount = total
                payment.save()

                # Guardar los logs en la base de datos
                StoreProductLog.objects.bulk_create(logs)

                serializer = SaleSerializer(sale)
                return Response(
                    {"sale": serializer.data, "cash_back": cash_back},
                    status=status.HTTP_200_OK,
                )

            # If no products remain, delete the sale
            cash_back = sale.total
            sale.delete()

        # Guardar los logs en caso de que la venta se haya eliminado completamente
        StoreProductLog.objects.bulk_create(logs)

        return Response({"sale": {}, "cash_back": cash_back}, status=status.HTTP_200_OK)



from escpos.printer import Network

@method_decorator(get_store(), name="dispatch")
class PrintTicketView(APIView):
    def post(self, request, *args, **kwargs):
        store = self.request.store

        try:

            printer = Printer.objects.get(store=store)
            # Obtener datos del ticket, por ejemplo desde request.data
            ticket_data = request.data.get("text", "Ticket sin contenido")
            printer.send_print(ticket_data)

            return Response({"message": "Ticket enviado a la impresora"})
        except Exception as e:
            print(e)
            return Response({"error": str(e)}, status=400)
