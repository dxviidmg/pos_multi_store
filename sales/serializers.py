from rest_framework import serializers

from clients.serializers import ClientSerializer
from .models import ProductSale, Sale


class ProductSaleSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source='product.code', read_only=True)
    name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ProductSale
        exclude = ["product", "sale"]


class SaleSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source='seller.username', read_only=True)
    is_cancelable = serializers.SerializerMethodField()
    payments_methods = serializers.SerializerMethodField()
    client = ClientSerializer()
    products_sale = ProductSaleSerializer(many=True)
    is_repeated = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()
    paid = serializers.DecimalField(source='get_paid', max_digits=10, decimal_places=2, read_only=True)

    def get_is_cancelable(self, obj):
        return obj.is_cancelable()

    def get_payments_methods(self, obj):
        return obj.get_payments_methods_display()

    def get_is_repeated(self, obj):
        return obj.is_repeated()

    def get_reference(self, obj):
        return obj.get_reference()

    class Meta:
        model = Sale
        fields = "__all__"


class SaleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = ["id", "total", "client", "reservation_in_progress"]


class SaleSerializer2(serializers.ModelSerializer):
    products_sale = ProductSaleSerializer(many=True)

    class Meta:
        model = Sale
        fields = "__all__"


class SaleAuditSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.get_full_name', read_only=True)

    class Meta:
        model = Sale
        fields = ["id", "created_at", "store_name"]
