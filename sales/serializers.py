from rest_framework import serializers
from .models import Sale, ProductSale
from clients.serializers import ClientSerializer


class ProductSaleSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()

    def get_description(self, obj):
        return obj.product.get_description()

    class Meta:
        model = ProductSale
        exclude = ["product", "sale"]


class SaleSerializer(serializers.ModelSerializer):
    saler_username = serializers.SerializerMethodField()
    is_cancelable = serializers.SerializerMethodField()
    payments_methods = serializers.SerializerMethodField()
    client = ClientSerializer()
    products_sale = ProductSaleSerializer(many=True)
    is_duplicate = serializers.SerializerMethodField()

    def get_saler_username(self, obj):
        return obj.saler.username

    def get_is_cancelable(self, obj):
        return obj.is_cancelable()

    def get_payments_methods(self, obj):
        return obj.get_payments_methods_display()

    def get_is_duplicate(self, obj):
        previous_obj = Sale.objects.filter(pk__lt=obj.pk, store=obj.store).order_by('-pk').first()
        diff = obj.created_at - previous_obj.created_at
        return diff.total_seconds() < 1
    
    class Meta:
        model = Sale
        fields = "__all__"


class SaleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = ["total", "client"]
