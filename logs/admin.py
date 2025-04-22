from django.contrib import admin
from .models import StoreProductLog

# Register your models here.

@admin.register(StoreProductLog)
class StoreProductLogAdmin(admin.ModelAdmin):
    search_fields = ['id', 'store_product__product__code']
    list_display = ['id', 'created_at', 'store_product__product__code']
