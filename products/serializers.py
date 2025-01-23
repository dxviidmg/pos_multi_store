from rest_framework import serializers
from .models import Product, StoreProduct, Transfer, Store, Brand
from django.core.exceptions import ValidationError


class BrandSerializer(serializers.ModelSerializer):
	product_count = serializers.SerializerMethodField()

	def get_product_count(self, obj):
		return obj.get_product_count()

	class Meta:
		model = Brand
		exclude = ["tenant"]


class StoreProductBaseSerializer(serializers.ModelSerializer):
	product_code = serializers.SerializerMethodField()
	product_brand = serializers.SerializerMethodField()
	product_name = serializers.SerializerMethodField()

	def get_product_code(self, obj):
		return obj.product.code

	def get_product_brand(self, obj):
		return obj.product.brand.name
	
	def get_product_name(self, obj):
		return obj.product.name
		


	class Meta:
		model = StoreProduct
		fields = "__all__"



class StoreProductSerializer(StoreProductBaseSerializer):
	product_id = serializers.SerializerMethodField()
	product_description = serializers.SerializerMethodField()
	available_stock = serializers.SerializerMethodField()
	reserved_stock = serializers.SerializerMethodField()

	prices = serializers.SerializerMethodField()
	stock_in_other_stores = serializers.SerializerMethodField()

	def get_product_id(self, obj):
		return obj.product.id


	def get_product_description(self, obj):
		return obj.product.get_description()

	def get_available_stock(self, obj):
		return obj.calculate_available_stock()

	def get_reserved_stock(self, obj):
		return obj.calculate_reserved_stock()
	

	def get_prices(self, obj):
		return {
			"unit_sale_price": obj.product.unit_sale_price,
			"wholesale_sale_price": obj.product.wholesale_sale_price,
			"min_wholesale_quantity": obj.product.min_wholesale_quantity,
			"apply_wholesale": obj.product.apply_wholesale(),
			"apply_wholesale_price_on_client_discount": obj.product.apply_wholesale_price_on_client_discount, 
		
		}

	def get_stock_in_other_stores(self, obj):
		# Optimize by pre-filtering and reducing unnecessary calculations
		return [
			{
				"store_id": str(sp.store.id),
				"store_name": str(sp.store),
				"available_stock": sp.calculate_available_stock(),
			}
			for sp in StoreProduct.objects.filter(product=obj.product).exclude(id=obj.id).exclude(stock=0)
			if sp.calculate_available_stock() > 0
		]


class TransferSerializer(serializers.ModelSerializer):
	product_code = serializers.SerializerMethodField()
	product_description = serializers.SerializerMethodField()
	description = serializers.SerializerMethodField()

	def get_product_code(self, obj):
		return obj.product.code

	def get_product_description(self, obj):
		return obj.product.get_description()

	def get_description(self, obj):
		store = self.context["request"].store
		if store == obj.origin_store:
			return "Le proveere este producto a " + obj.destination_store.__str__()
		elif store == obj.destination_store:
			return "Le solicite este producto a " + obj.origin_store.__str__()
		return "No tengo gerencia entre traspaso"

	class Meta:
		model = Transfer
		fields = "__all__"


class StoreSerializer(serializers.ModelSerializer):
	full_name = serializers.SerializerMethodField()
	store_type_display = serializers.SerializerMethodField()

	def get_full_name(self, obj):
		return obj.get_full_name()

	def get_store_type_display(self, obj):
		return obj.get_store_type_display()

	class Meta:
		model = Store
		fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):

	brand_name = serializers.SerializerMethodField()
	apply_wholesale = serializers.SerializerMethodField()

	def get_brand_name(self, obj):
		return obj.brand.name

	def get_apply_wholesale(self, obj):
		return obj.apply_wholesale()

	class Meta:
		model = Product
		fields = "__all__"

	def validate(self, data):
		request = self.context.get("request")
		method = request.method if request else None

		if method == "POST":
			if Product.objects.filter(
				code=data["code"], brand__tenant=data["brand"].tenant
			).exists():
				raise ValidationError(
					{"code": "product with this code already exists."}
				)

		return data
