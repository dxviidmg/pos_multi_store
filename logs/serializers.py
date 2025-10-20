from rest_framework import serializers
from .models import StoreProductLog
from products.serializers import ProductSerializer


class StoreProductLogSerializer(serializers.ModelSerializer):

    description = serializers.SerializerMethodField()
    difference = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    is_consistent = serializers.SerializerMethodField()

    def get_description(self, obj):
        return obj.get_description()

    def get_difference(self, obj):
        return obj.calculate_difference()

    def get_user_username(self, obj):
        return obj.user.username

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

    product_code = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    store_name = serializers.SerializerMethodField()

    def get_product_code(self, obj):
        return obj.store_product.product.code

    def get_product_name(self, obj):
        return obj.store_product.product.get_description()

    def get_store_name(self, obj):
        return obj.store_product.store.get_full_name()

    def get_is_consistent(self, obj):
        return obj.is_consistent()
    
    class Meta:
        model = StoreProductLog
        fields = ["id", "created_at", "product_code", "product_name", "store_name"]