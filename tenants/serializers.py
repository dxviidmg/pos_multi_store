from rest_framework import serializers
from .models import Payment, Plan, Tenant


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "short_name", "is_sandbox", 
                  "displays_stock_in_storages", "created_at", 'create_products_on_sale']
        read_only_fields = ["id", "short_name", "is_sandbox", "created_at"]


class TenantCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "short_name"]
        read_only_fields = ["id"]


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "name", "price", "stores", "billing_type"]
