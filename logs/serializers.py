from rest_framework import serializers

from products.serializers import ProductSerializer
from .models import ProductPriceLog, StoreProductLog


class StoreProductLogSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source='get_description', read_only=True)
    difference = serializers.IntegerField(source='calculate_difference', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    is_consistent = serializers.SerializerMethodField()

    def get_is_consistent(self, obj):
        return obj.is_consistent()

    class Meta:
        model = StoreProductLog
        fields = "__all__"


class StoreProductLogSerializer2(StoreProductLogSerializer):
    product = serializers.SerializerMethodField()

    def get_product(self, obj):
        return ProductSerializer(obj.store_product.product).data


class StoreProductLogAuditSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='store_product.product.code', read_only=True)
    product_name = serializers.CharField(source='store_product.product.get_description', read_only=True)
    store_name = serializers.CharField(source='store_product.store.get_full_name', read_only=True)

    class Meta:
        model = StoreProductLog
        fields = ["id", "created_at", "product_code", "product_name", "store_name"]


class ProductPriceLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    product_name = serializers.CharField(source='product.get_description', read_only=True)
    field_display = serializers.SerializerMethodField()

    FIELD_LABELS = {
        'cost': 'Costo',
        'unit_price': 'Precio menudeo',
        'wholesale_price': 'Precio mayoreo',
        'min_wholesale_quantity': 'Cantidad mínima mayoreo',
    }

    def get_field_display(self, obj):
        return self.FIELD_LABELS.get(obj.field, obj.field)

    class Meta:
        model = ProductPriceLog
        fields = ['id', 'product', 'product_name', 'user_username', 'field', 'field_display', 'previous_value', 'new_value', 'created_at']
