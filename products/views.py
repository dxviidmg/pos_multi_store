from rest_framework import viewsets
from .serializers import (
	StoreProductSerializer,
	TransferSerializer,
	StoreSerializer,
	ProductSerializer,
	BrandSerializer
)
from .models import StoreProduct, Product, Store, Transfer, Brand
from django.db.models import Q
from functools import reduce
from operator import or_
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
from django.db import transaction


class StoreProductViewSet(viewsets.ModelViewSet):
	serializer_class = StoreProductSerializer

	def get_queryset(self):
		q = self.request.GET.get("q", "")
		code = self.request.GET.get("code", "")

		# Intentar obtener la tienda, retornar un queryset vacío si no existe
		store = self.request.user.get_store()

		# Filtrar por código del producto si está especificado
		if code:
			product = Product.objects.filter(code=code).first()
			return (
				StoreProduct.objects.filter(product=product, store=store)
				if product
				else StoreProduct.objects.none()
			)

		# Construir la consulta de búsqueda en `Product` si se proporciona `q`
		filters = Q()
		if q:
			filters |= (
				Q(brand__name__icontains=q)
				| Q(code__icontains=q)
				| Q(name__icontains=q)
			)

		# Obtener productos y filtrar `StoreProduct` según la tienda
		product_queryset = Product.objects.filter(filters).select_related("brand")[:5]
		return StoreProduct.objects.filter(
			product__in=product_queryset, store=store
		).prefetch_related("product")


class TransferViewSet(viewsets.ModelViewSet):
	serializer_class = TransferSerializer

	def get_queryset(self):
		store = self.request.user.get_store()

		return Transfer.objects.filter(
			Q(origin_store=store) | Q(destination_store=store), transfer_datetime=None
		)

class ProductViewSet(viewsets.ModelViewSet):
	serializer_class = ProductSerializer

	def get_queryset(self):
		tenant = self.request.user.get_tenant()   
		return Product.objects.filter(brand__tenant=tenant)



class StoreViewSet(viewsets.ModelViewSet):
	serializer_class = StoreSerializer

	def get_queryset(self):
		store = self.request.user.get_store()

		tenant = self.request.user.get_tenant()
		
		return Store.objects.filter(store_type='T', tenant=tenant).exclude(id=store.id)


class ConfirmProductTransfersView(APIView):
	@transaction.atomic  # Decorador para asegurar la atomicidad de todo el método
	def post(self, request):
		transfer_list = request.data.get("transfers")
		destination_store_id = request.data.get("destination_store")
		origin_store = self.request.user.get_store()

		transfers_to_process = []

		for transfer_item in transfer_list:
			product_id = transfer_item['product_id']
			quantity = transfer_item['quantity']

			transfer_filter = {
				"product": product_id,
				"quantity": quantity,
				"destination_store": destination_store_id,
				"origin_store": origin_store.id,
				"transfer_datetime": None
			}

			try:
				transfer_record = Transfer.objects.get(**transfer_filter)
			except Transfer.DoesNotExist:
				return Response(
					{"status": "Transfer not found"}, status=status.HTTP_404_NOT_FOUND
				)

			transfers_to_process.append({'transfer': transfer_record, 'quantity': quantity})

		for transfer_info in transfers_to_process:
			transfer = transfer_info['transfer']

			# Update the transfer timestamp
			transfer.transfer_datetime = datetime.now()
			transfer.save()

			# Update the stock in the destination store
			destination_store = transfer.destination_store

			destination_stock_filter = {"product": transfer.product, "store": destination_store}
			origin_stock_filter = {"product": transfer.product, "store": transfer.origin_store}

			try:
				destination_store_product = StoreProduct.objects.get(**destination_stock_filter)
				destination_store_product.stock += transfer_info['quantity']
				destination_store_product.save()

				# Update the stock in the origin store
				origin_store_product = StoreProduct.objects.get(**origin_stock_filter)
				origin_store_product.stock -= transfer_info['quantity']
				origin_store_product.save()

			except StoreProduct.DoesNotExist:
				return Response(
					{"status": "Product stock not found in one of the stores"}, 
					status=status.HTTP_404_NOT_FOUND
				)

		return Response(
			{"status": "Transfer confirmed"}, status=status.HTTP_200_OK
		)
	



class ConfirmDistributionView(APIView):
	@transaction.atomic  # Decorador para asegurar la atomicidad de todo el método
	def post(self, request):
		products = request.data.get("products")
		destination_store_id = request.data.get("destination_store")
		origin_store = self.request.user.get_store()

		if not products or not destination_store_id:
			return Response(
				{"status": "Missing required data"},
				status=status.HTTP_400_BAD_REQUEST
			)

		for product_data in products:
			product_id = product_data.get('product_id')
			quantity = product_data.get('quantity')

			if not product_id or quantity is None or quantity <= 0:
				return Response(
					{"status": "Invalid product data"},
					status=status.HTTP_400_BAD_REQUEST
				)

			try:
				# Obtener y actualizar el stock en la tienda de destino
				destination_store_product = StoreProduct.objects.get(
					product=product_id, store=destination_store_id
				)
				destination_store_product.stock += quantity
				destination_store_product.save()

				# Obtener y actualizar el stock en la tienda de origen
				origin_store_product = StoreProduct.objects.get(
					product=product_id, store=origin_store.id
				)
				if origin_store_product.stock < quantity:
					return Response(
						{"status": f"Insufficient stock for product {product_id}"},
						status=status.HTTP_400_BAD_REQUEST
					)
				origin_store_product.stock -= quantity
				origin_store_product.save()

			except StoreProduct.DoesNotExist:
				return Response(
					{"status": "Product stock not found in one of the stores"},
					status=status.HTTP_404_NOT_FOUND
				)

		return Response({"status": "Transfer confirmed"}, status=status.HTTP_200_OK)
	


class BrandViewSet(viewsets.ModelViewSet):
	serializer_class = BrandSerializer

	def get_queryset(self):
		tenant = self.request.user.get_tenant()   
		return Brand.objects.filter(tenant=tenant)
	

	def perform_create(self, serializer):
		tenant = self.request.user.get_tenant()
		sale_instance = serializer.save(tenant=tenant)
		return sale_instance
		
	
class AddProductsView(APIView):
	@transaction.atomic
	def post(self, request):
		product_list = request.data.get("products")
		user_store = self.request.user.get_store()

		product_ids = [product_data['product_id'] for product_data in product_list]
		store_products = StoreProduct.objects.filter(product__in=product_ids, store=user_store)

		store_product_dict = {store_product.product_id: store_product for store_product in store_products}

		for product_data in product_list:
			product_id = product_data['product_id']
			if product_id in store_product_dict:
				store_product = store_product_dict[product_id]
				store_product.stock += product_data['quantity']

		# Bulk update all modified store products
		StoreProduct.objects.bulk_update(store_products, ['stock'])

		return Response(
			{"status": "Stock increment confirmed"}, status=status.HTTP_200_OK
		)