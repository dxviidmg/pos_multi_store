from django.contrib import admin
from .models import Sale, SaleProduct, Payment


admin.site.register(Sale)
admin.site.register(SaleProduct)
admin.site.register(Payment)