from datetime import date, datetime

from django.core.exceptions import ValidationError
from rest_framework import serializers

from .models import Client, Discount


class DiscountSerializer(serializers.ModelSerializer):
	discount_percentage_complement = serializers.SerializerMethodField()

	def get_discount_percentage_complement(self, obj):
		return obj.get_discount_percentage_complement()

	class Meta:
		model = Discount
		exclude =["tenant"]


	def validate(self, data):
		request = self.context.get('request')
		method = request.method if request else None

		tenant = request.user.get_tenant()

		if method == 'POST':
			if  Discount.objects.filter(discount_percentage=data['discount_percentage'], tenant=tenant).exists():
				raise ValidationError({"discount_percentage": "discount with this discount percentage already exists."})

		return data
	

class ClientSerializer(serializers.ModelSerializer):
	full_name = serializers.SerializerMethodField()
	discount_percentage = serializers.SerializerMethodField()
	discount_percentage_complement = serializers.SerializerMethodField()
	total_sales_amount = serializers.SerializerMethodField()

	def get_full_name(self, obj):
		return obj.get_full_name()

	def get_discount_percentage(self, obj):
		return obj.discount.discount_percentage

	def get_discount_percentage_complement(self, obj):
		return obj.discount.get_discount_percentage_complement()
	
	def get_total_sales_amount(self, obj):
		start_date_str = self.context.get("start_date")
		end_date_str = self.context.get("end_date")

		start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else date.today()
		end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else date.today()
		return obj.get_total_sales_amount(start_date, end_date)

	class Meta:
		model = Client
		fields = "__all__"