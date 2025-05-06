from rest_framework import serializers
from .models import Sale, ProductSale
from clients.serializers import ClientSerializer


class ProductSaleSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.product.name

    class Meta:
        model = ProductSale
        exclude = ["product", "sale"]


class SaleSerializer(serializers.ModelSerializer):
    seller_username = serializers.SerializerMethodField()
    is_cancelable = serializers.SerializerMethodField()
    payments_methods = serializers.SerializerMethodField()
    client = ClientSerializer()
    products_sale = ProductSaleSerializer(many=True)
    is_duplicate = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()
    refunded = serializers.SerializerMethodField()
    paid = serializers.SerializerMethodField()

    
    def get_refunded(self, obj):
        return obj.get_refunded()
    def get_seller_username(self, obj):
        return obj.seller.username

    def get_is_cancelable(self, obj):
        return obj.is_cancelable()

    def get_payments_methods(self, obj):
        return obj.get_payments_methods_display()

    def get_is_duplicate(self, obj):
        previous_obj = Sale.objects.filter(pk__lt=obj.pk, store=obj.store).order_by('-pk').first()
        if previous_obj:
            diff = obj.created_at - previous_obj.created_at
            return diff.total_seconds() < 1
        return False
    
    def get_reference(self, obj):
        return obj.get_reference()
    
    def get_paid(self, obj):
        return obj.get_paid()
    
    class Meta:
        model = Sale
        fields = "__all__"


class SaleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = ["total", "client", "reservation_in_progress"]



class SaleSerializer2(serializers.ModelSerializer):

    products_sale = ProductSaleSerializer(many=True)
    refunded = serializers.SerializerMethodField()


    
    def get_refunded(self, obj):
        return obj.get_refunded()
    

    
    class Meta:
        model = Sale
        fields = "__all__"