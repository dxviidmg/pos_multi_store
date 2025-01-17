from rest_framework import serializers
from .models import Sale, SaleProduct
from clients.serializers import ClientSerializer
from products.serializers import ProductSerializer


class SaleProductSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()

    def get_description(self, obj):
        return obj.product.get_description()

    class Meta:
        model = SaleProduct
        exclude = ['product', 'sale']


class SaleSerializer(serializers.ModelSerializer):
    client = ClientSerializer()

    products = SaleProductSerializer(many=True)

    class Meta:
        model = Sale
        fields = "__all__"


class SaleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = ["total", "client"]

