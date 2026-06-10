from django.contrib import admin
from .models import Tenant, Payment, Plan, Subscription, SubscriptionPayment


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']

admin.site.register(Payment)
admin.site.register(Plan)
admin.site.register(Subscription)
admin.site.register(SubscriptionPayment)