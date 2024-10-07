from django.contrib import admin
from .models import Store, Product, StoreProduct


class ProductAdmin(admin.ModelAdmin):
    pass


admin.site.register(Product, ProductAdmin)

class StoreAdmin(admin.ModelAdmin):
    pass


admin.site.register(Store, StoreAdmin)


class StoreProductAdmin(admin.ModelAdmin):
    pass


admin.site.register(StoreProduct, StoreProductAdmin)