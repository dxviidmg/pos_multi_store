from django.contrib import admin
from .models import Tenant, Payment, Plan, Subscription, SubscriptionPayment


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'plan_name']

    def plan_name(self, obj):
        return obj.plan.name if obj.plan else '-'
    plan_name.short_description = 'Plan'

admin.site.register(Payment)

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'stores', 'billing_type']
    ordering = ['id']

admin.site.register(Subscription)
admin.site.register(SubscriptionPayment)