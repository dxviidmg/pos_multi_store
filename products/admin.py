from django.contrib import admin
from .models import Store, Product, StoreProduct, Brand, Transfer


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = ['code', 'name']
    list_display = ['brand__name', 'code', 'name']
    list_filter = ['brand__name']

@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
    search_fields = ['product__id', 'product__code', 'product__name']
    list_display = ['id', 'product__id', 'product__name', 'store__id', 'product__code', 'store__name', 'stock']

admin.site.register(Store)
admin.site.register(Brand)

@admin.register(Transfer)
class ProductTransferAdmin(admin.ModelAdmin):
    search_fields = ['product__id', 'product__code', 'product__name']
    list_display = ['id', 'product__id', 'product__name', 'product__code', 'origin_store__id', 'destination_store__id']