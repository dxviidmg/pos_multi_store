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