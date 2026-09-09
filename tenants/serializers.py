from rest_framework import serializers
from .models import Payment, Plan, Subscription, Tenant


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


class SubscriptionSerializer(serializers.ModelSerializer):
    card_expiration = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ["id", "tenant", "mp_subscription_id", "payer_email",
                  "amount", "status", "payment_method_id", "created_at",
                  "card_brand", "card_last_four", "card_expiration_month",
                  "card_expiration_year", "card_expiration"]
        read_only_fields = fields

    def get_card_expiration(self, obj):
        if obj.card_expiration_month and obj.card_expiration_year:
            return f"{obj.card_expiration_month:02d}/{str(obj.card_expiration_year)[-2:]}"
        return None
