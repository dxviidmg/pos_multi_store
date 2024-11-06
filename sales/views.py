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


# Create your views here.
class SaleViewSet(viewsets.ModelViewSet):
	def get_serializer_class(self):
		if self.request.method == "POST":
			return SaleCreateSerializer
		return SaleSerializer

	def get_queryset(self):
		today = date.today()
		return Sale.objects.filter(saler=self.request.user, created_at__date=today)

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

		# Save the sale and associate it with the current user
		sale_instance = serializer.save(saler=self.request.user)

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
        today = date.today()
        
        user_sales = Sale.objects.filter(saler=self.request.user, created_at__date=today)
        total_sales_sum = user_sales.aggregate(total=Sum("total"))['total'] or 0
        related_payments = Payment.objects.filter(sale__in=user_sales)
        payments_by_method = related_payments.values("payment_method").annotate(total_amount=Sum("amount"))
        total_payments_sum = related_payments.aggregate(total=Sum("amount"))['total'] or 0

        # Obtener significados de métodos de pago
        payment_methods_meaning = dict(Payment.PAYMENT_METHOD_CHOICES)
        payments_by_method = [
            {
                "payment_method": payment_methods_meaning.get(payment["payment_method"], payment["payment_method"]),
                "total_amount": payment["total_amount"]
            }
            for payment in payments_by_method
        ]

        return Response(
            {
                "is_balance_matched": total_sales_sum == total_payments_sum,
                "total_sales_sum": total_sales_sum,
                "total_payments_sum": total_payments_sum,
                "payments_by_method": payments_by_method,
            }
        )