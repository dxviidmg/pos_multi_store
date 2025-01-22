from django.contrib import admin
from .models import Tenant, Payment


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']

admin.site.register(Payment)