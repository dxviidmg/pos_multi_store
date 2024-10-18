from rest_framework import serializers
from .models import Product, StoreProduct


class StoreProductSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    brand_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()

    def get_product_name(self, obj):
        return obj.product.name

    def get_brand_name(self, obj):
        return obj.product.brand.name

    def get_category_name(self, obj):
        return obj.product.category.name

    class Meta:
        model = StoreProduct
        fields = "__all__"