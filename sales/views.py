from django.shortcuts import render
from rest_framework import viewsets
from .serializers import SaleSerializer, SaleCreateSerializer
from .models import Sale
from products.models import StoreProduct
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
        
        # List to hold the StoreProduct instances that need to be updated
        updated_store_products = []

        # Using a transaction to ensure all updates are executed together
        with transaction.atomic():
            for product_data in store_products_data:
                product_instance = StoreProduct.objects.get(id=product_data['id'])
                product_instance.stock -= product_data['quantity']
                updated_store_products.append(product_instance)

            # Perform a bulk update on the stock of StoreProduct instances
            StoreProduct.objects.bulk_update(updated_store_products, ['stock'])

        # Save the sale and associate it with the current user
        return serializer.save(saler=self.request.user)