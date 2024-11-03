from rest_framework import serializers
from .models import Discount, Client


class DiscountSerializer(serializers.ModelSerializer):
    discount_percentage_complement = serializers.SerializerMethodField()

    def get_discount_percentage_complement(self, obj):
        return obj.get_discount_percentage_complement()

    class Meta:
        model = Discount
        fields = "__all__"




class ClientSerializer(serializers.ModelSerializer):
    discount_percentage = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_discount_percentage(self, obj):
        return obj.discount.discount_percentage

    class Meta:
        model = Client
        fields = "__all__"