from django.shortcuts import render
from rest_framework import viewsets
from .serializers import SaleSerializer, SaleCreateSerializer
from .models import Sale, SaleProduct, Payment
from products.models import StoreProduct, Product
from django.db import transaction


# Create your views here.
class SaleViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SaleCreateSerializer
        return SaleSerializer  

    def get_queryset(self):
        return Sale.objects.filter(saler=self.request.user)

    def perform_create(self, serializer):
        store_products_data = self.request.data.get('store_products')
        payments_data = self.request.data.get('payments')

        # List to hold the StoreProduct instances that need to be updated
        updated_store_products = []

        # Using a transaction to ensure all updates are executed together
        with transaction.atomic():
            for product_data in store_products_data:
                product_store = StoreProduct.objects.get(id=product_data['id'])
                product_store.stock -= product_data['quantity']
                updated_store_products.append(product_store)

            # Perform a bulk update on the stock of StoreProduct instances
            StoreProduct.objects.bulk_update(updated_store_products, ['stock'])

        # Save the sale and associate it with the current user
        sale_instance = serializer.save(saler=self.request.user)

        for product_data in store_products_data:
            product_store = StoreProduct.objects.get(id=product_data['id'])
            product = product_store.product

            data = {'sale': sale_instance, 'product': product, 'quantity': product_data['quantity'], 'price': product_data['price']}
            SaleProduct.objects.create(**data)



        print('payments_data', payments_data)
        for payment_data in payments_data:
            print(payment_data)


            data = {'sale': sale_instance, 'payment_method': payment_data['payment_method'], 'amount': payment_data['amount']}
            Payment.objects.create(**data)



        return sale_instance