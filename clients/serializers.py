from datetime import date, datetime

from django.core.exceptions import ValidationError
from rest_framework import serializers

from .models import Client, Discount


class DiscountSerializer(serializers.ModelSerializer):
    discount_percentage_complement = serializers.IntegerField(
        source='get_discount_percentage_complement', read_only=True
    )

    class Meta:
        model = Discount
        exclude = ["tenant"]

    def validate(self, data):
        request = self.context.get('request')
        if request and request.method == 'POST':
            tenant = request.user.get_tenant()
            if Discount.objects.filter(discount_percentage=data['discount_percentage'], tenant=tenant).exists():
                raise ValidationError({"discount_percentage": "discount with this discount percentage already exists."})
        return data


class ClientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    discount_percentage = serializers.IntegerField(source='discount.discount_percentage', read_only=True)
    discount_percentage_complement = serializers.IntegerField(
        source='discount.get_discount_percentage_complement', read_only=True
    )
    total_sales_amount = serializers.SerializerMethodField()

    def get_total_sales_amount(self, obj):
        start_date_str = self.context.get("start_date")
        end_date_str = self.context.get("end_date")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else date.today()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else date.today()
        return obj.get_total_sales_amount(start_date, end_date)

    class Meta:
        model = Client
        fields = "__all__"
