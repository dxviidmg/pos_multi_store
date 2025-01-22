from django.contrib import admin
from .models import Sale, Payment, ProductSale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'saler']


@admin.register(ProductSale)
class ProductSaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'sale_id', 'product_id']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['sale__id', 'sale__created_at']

