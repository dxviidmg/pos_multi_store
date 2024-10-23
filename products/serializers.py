from rest_framework import serializers
from .models import Product, StoreProduct


class StoreProductSerializer(serializers.ModelSerializer):
    product_code = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_price = serializers.SerializerMethodField()
    brand_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    stock_in_other_stores = serializers.SerializerMethodField()
    
    def get_product_code(self, obj):
        return obj.product.code

    def get_product_name(self, obj):
        return obj.product.name

    def get_product_price(self, obj):
        return obj.product.public_sale_price

    def get_brand_name(self, obj):
        return obj.product.brand.name

    def get_category_name(self, obj):
        return obj.product.category.name

    def get_stock_in_other_stores(self, obj):
        sps = StoreProduct.objects.filter(product=obj.product).exclude(id=obj.id).values('store__name', 'stock')
        return sps

    class Meta:
        model = StoreProduct
        fields = "__all__"