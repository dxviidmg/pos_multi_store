from rest_framework import serializers
from .models import Product, StoreProduct


class StoreProductSerializer(serializers.ModelSerializer):
    product_code = serializers.SerializerMethodField()
    prices = serializers.SerializerMethodField()
    stock_in_other_stores = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    def get_product_code(self, obj):
        return obj.product.code

    def get_description(self, obj):
        return obj.product.get_description()

    def get_prices(self, obj):
        return {
            "unit_sale_price": obj.product.unit_sale_price,
            "wholesale_sale_price": obj.product.wholesale_sale_price,
            "min_wholesale_quantity": obj.product.min_wholesale_quantity,
            "apply_wholesale": obj.product.wholesale_sale_price is not None
            and obj.product.min_wholesale_quantity is not None,
        }

    def get_stock_in_other_stores(self, obj):
        return [
            {"store_name": str(sp.store), "stock": sp.stock}
            for sp in StoreProduct.objects.filter(product=obj.product).exclude(
                id=obj.id).exclude(stock=0)
        ]

    class Meta:
        model = StoreProduct
        fields = "__all__"
