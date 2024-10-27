from django.shortcuts import render
from rest_framework import viewsets
from .serializers import SaleSerializer, SaleCreateSerializer
from .models import Sale
from products.models import StoreProduct

# Create your views here.
class SaleViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SaleCreateSerializer  # Serializador específico para POST
        return SaleSerializer  

    def get_queryset(self):
        return Sale.objects.filter(saler=self.request.user)




    def perform_create(self, serializer):

        store_products = self.request.data.get('store_products')
        for store_product_data in store_products:
            store_product = StoreProduct.objects.get(id=store_product_data['id'])
            store_product.stock = store_product.stock - store_product_data['quantity']
            store_product.save()

        return serializer.save(saler=self.request.user)