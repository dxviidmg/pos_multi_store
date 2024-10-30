from django.contrib import admin
from .models import Sale, SaleProduct, Payment


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['created_at']

admin.site.register(SaleProduct)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['sale__id', 'sale__created_at']

