from django.contrib import admin
from .models import Store, Product, StoreProduct, Brand, Category


class ProductAdmin(admin.ModelAdmin):
    search_fields = ['code', 'name']


admin.site.register(Product, ProductAdmin)

class StoreAdmin(admin.ModelAdmin):
    pass


admin.site.register(Store, StoreAdmin)


class StoreProductAdmin(admin.ModelAdmin):
    pass


admin.site.register(StoreProduct, StoreProductAdmin)


class BrandAdmin(admin.ModelAdmin):
    pass


admin.site.register(Brand, BrandAdmin)


class CategoryAdmin(admin.ModelAdmin):
    pass


admin.site.register(Category, CategoryAdmin)