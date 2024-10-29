from django.contrib import admin
from .models import Store, Product, StoreProduct, Brand


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = ['code', 'name']

# Registrar los demás modelos directamente sin clases de administración innecesarias
admin.site.register(Store)
admin.site.register(StoreProduct)
admin.site.register(Brand)