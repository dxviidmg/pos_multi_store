from rest_framework import serializers
from .models import Payment, Tenant


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "short_name", "is_sandbox", 
                  "displays_stock_in_storages", "created_at"]
        read_only_fields = ["id", "short_name", "is_sandbox", "created_at"]
