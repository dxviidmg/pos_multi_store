from rest_framework import serializers
from .models import Product, StoreProduct, ProductTransfer, Store


class StoreProductSerializer(serializers.ModelSerializer):
	product_id = serializers.SerializerMethodField()
	product_code = serializers.SerializerMethodField()
	prices = serializers.SerializerMethodField()
	stock_in_other_stores = serializers.SerializerMethodField()
	description = serializers.SerializerMethodField()
	available_stock = serializers.SerializerMethodField()
	reserved_stock = serializers.SerializerMethodField()

	def get_product_id(self, obj):
		return obj.product.id

	def get_product_code(self, obj):
		return obj.product.code

	def get_description(self, obj):
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
			"apply_wholesale": obj.product.wholesale_sale_price is not None
			and obj.product.min_wholesale_quantity is not None,
		}

	def get_stock_in_other_stores(self, obj):
		return [
			{
				"store_id": str(sp.store.id),
				"store_name": str(sp.store),
				"available_stock": sp.calculate_available_stock(),
			}
			for sp in StoreProduct.objects.filter(product=obj.product)
			.exclude(id=obj.id)
			.exclude(stock=0) 
			if sp.calculate_available_stock() > 0  # Excluir si calculate_stock_to_share() es 0
		]

	class Meta:
		model = StoreProduct
		fields = "__all__"




class ProductTransferSerializer(serializers.ModelSerializer):
	product_code = serializers.SerializerMethodField()
	product_description = serializers.SerializerMethodField()
	description = serializers.SerializerMethodField()

	def get_product_code(self, obj):
		return obj.product.code

	def get_product_description(self, obj):
		return obj.product.get_description()

	def get_description(self, obj):
		store = Store.objects.get(manager=self.context['request'].user)
		if store == obj.origin_store:
			return 'Le proveere este producto a ' + obj.destination_store.__str__()
		elif store == obj.destination_store:
			return 'Le solicite este producto a ' + obj.origin_store.__str__()
		return 'No tengo gerencia entre traspaso'

	class Meta:
		model = ProductTransfer
		fields = "__all__"


class StoreSerializer(serializers.ModelSerializer):
	full_name = serializers.SerializerMethodField()

	def get_full_name(self, obj):
		return obj.get_full_name()

	class Meta:
		model = Store
		fields = "__all__"