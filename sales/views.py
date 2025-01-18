from django.shortcuts import render
from rest_framework import viewsets
from .serializers import SaleSerializer, SaleCreateSerializer
from .models import Sale, SaleProduct, Payment
from products.models import StoreProduct, Product
from django.db import transaction
from datetime import date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum
import pandas as pd


# Create your views here.
class SaleViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.method == "POST":
            return SaleCreateSerializer
        return SaleSerializer

    def get_queryset(self):
        date = self.request.GET.get("date")
        store = self.request.user.get_store()
        return Sale.objects.filter(store=store, created_at__date=date)

    def perform_create(self, serializer):
        store_products_data = self.request.data.get("store_products")
        payments_data = self.request.data.get("payments")

        # List to hold the StoreProduct instances that need to be updated
        updated_store_products = []

        # Using a transaction to ensure all updates are executed together
        with transaction.atomic():
            for product_data in store_products_data:
                product_store = StoreProduct.objects.get(id=product_data["id"])
                product_store.stock -= product_data["quantity"]
                updated_store_products.append(product_store)

            # Perform a bulk update on the stock of StoreProduct instances
            StoreProduct.objects.bulk_update(updated_store_products, ["stock"])

        store = self.request.user.get_store()
        # Save the sale and associate it with the current user
        sale_instance = serializer.save(store=store)

        for product_data in store_products_data:
            product_store = StoreProduct.objects.get(id=product_data["id"])
            product = product_store.product

            data = {
                "sale": sale_instance,
                "product": product,
                "quantity": product_data["quantity"],
                "price": product_data["price"],
            }
            SaleProduct.objects.create(**data)

        for payment_data in payments_data:
            data = {
                "sale": sale_instance,
                "payment_method": payment_data["payment_method"],
                "amount": payment_data["amount"],
            }
            Payment.objects.create(**data)

        return sale_instance


class DailyEarnings(APIView):
    def get(self, request):
        date = request.GET.get("date")
        store = request.user.get_store()
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
                    "total_amount": 'Si' if total_sales_sum == total_payments_sum else 'No',
                },
            ]
        )

        return Response(payments_by_method)


class SalesImportValidation(APIView):

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

        store = self.request.user.get_store()
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


class SalesImport(APIView):

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

        store = self.request.user.get_store()
        tenant = self.request.user.get_tenant()

        try:
            df = pd.read_excel(file_obj)
            self.validate_columns(df)
            df = self.rename_columns(df)

            for _, row in df.iterrows():

                code = row["code"]
                quantity = row["quantity"]

                # Intentar obtener el producto
                product = Product.objects.get(code=code, brand__tenant=tenant)
                store_product = StoreProduct.objects.get(product=product, store=store)

                store_product.stock -= quantity
                store_product.save()

                store = self.request.user.get_store()
                # Save the sale and associate it with the current user
                total = product.unit_sale_price * quantity
                sale_instance = Sale.objects.create(store=store, total=total)

                data = {
                    "sale": sale_instance,
                    "product": product,
                    "quantity": quantity,
                    "price": product.unit_sale_price,
                }
                SaleProduct.objects.create(**data)

                data = {
                    "sale": sale_instance,
                    "payment_method": "EF",
                    "amount": total,
                }
                Payment.objects.create(**data)

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
