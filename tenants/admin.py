from django.contrib import admin
from .models import Tenant, Payment, Plan, Subscription, SubscriptionPayment


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'plan_name']

    def plan_name(self, obj):
        return obj.plan.name if obj.plan else '-'
    plan_name.short_description = 'Plan'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'tenant', 'months', 'total', 'start_of_validity', 'end_of_validity', 'mp_external_reference']
    ordering = ['-id']

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'stores', 'billing_type']
    ordering = ['id']

admin.site.register(Subscription)
admin.site.register(SubscriptionPayment)