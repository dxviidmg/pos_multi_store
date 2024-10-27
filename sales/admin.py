from django.contrib import admin
from .models import Sale


class SaleAdmin(admin.ModelAdmin):
    pass

admin.site.register(Sale, SaleAdmin)