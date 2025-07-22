from django.contrib import admin
from .models import Store, Product, StoreProduct, Brand, Transfer, CashFlow, StoreWorker, Department


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = ['code', 'name']
    list_display = ['brand__name', 'code', 'name']
    list_filter = ['brand__tenant', 'brand__name']

@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
    search_fields = ['product__id', 'product__code', 'product__name']
    list_display = ['id', 'product__id', 'product__name', 'store__id', 'product__code', 'store__name', 'stock']
    list_filter = ['store__tenant', 'store']

admin.site.register(Brand)


@admin.register(Store)
class StoreProdutAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ['id', 'name', 'store_type', 'tenant', 'list_printers']
    list_filter = ['tenant', 'store_type']

    def list_printers(self, obj):
        return ", ".join([
            sp.printer.__str__() for sp in obj.printer.all()
        ])

    list_printers.short_description = "Printers"

@admin.register(Transfer)
class ProductTransferAdmin(admin.ModelAdmin):
    search_fields = ['product__id', 'product__code', 'product__name']
    list_display = ['id', 'product__id', 'product__name', 'product__code', 'origin_store__id', 'destination_store__id']


#@admin.register(StoreProductLog)
#class StoreProductLogAdmin(admin.ModelAdmin):
#    search_fields = ['id', 'store_product__product__code']
#    list_display = ['id', 'created_at', 'store_product__product__code']



admin.site.register(CashFlow)

admin.site.register(StoreWorker)

admin.site.register(Department)