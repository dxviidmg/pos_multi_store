from django.contrib import admin
from .models import Sale, Payment, ProductSale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'saler']

admin.site.register(ProductSale)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['sale__id', 'sale__created_at']

