from rest_framework import serializers
from .models import Discount, Client
from django.core.exceptions import ValidationError


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

	def get_full_name(self, obj):
		return obj.get_full_name()

	def get_discount_percentage(self, obj):
		return obj.discount.discount_percentage

	def get_discount_percentage_complement(self, obj):
		return obj.discount.get_discount_percentage_complement()

	class Meta:
		model = Client
		fields = "__all__"