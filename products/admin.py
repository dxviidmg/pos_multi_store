from django.contrib import admin
from .models import Store, Product, StoreProduct, Brand, ProductTransfer


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = ['code', 'name']

@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
    search_fields = ['product__code', 'product__name']
    list_display = ['id', 'product__id', 'product__name', 'store__id', 'product__code', 'store__name', 'stock']

admin.site.register(Store)
admin.site.register(Brand)
admin.site.register(ProductTransfer)