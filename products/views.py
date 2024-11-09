from rest_framework import viewsets
from .serializers import (
    StoreProductSerializer,
    ProductTransferSerializer,
    StoreSerializer,
    ProductSerializer,
    BrandSerializer
)
from .models import StoreProduct, Product, Store, ProductTransfer, Brand
from django.db.models import Q
from functools import reduce
from operator import or_
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
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


class ProductTransferViewSet(viewsets.ModelViewSet):
    serializer_class = ProductTransferSerializer

    def get_queryset(self):
        store = self.request.user.get_store()

        return ProductTransfer.objects.filter(
            Q(origin_store=store) | Q(destination_store=store), transfer_datetime=None
        )

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()



class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = StoreSerializer

    def get_queryset(self):
        store = self.request.user.get_store()

        return Store.objects.exclude(id=store.id)


class ConfirmProductTransfers(APIView):
    def post(self, request):
        transfers_data = request.data.get("transfers")
        destination_store = request.data.get("destination_store")
        origin_store = self.request.user.get_store()

        transfers_to_update = []
        for transfer_data in transfers_data:
            data = {
                "product": transfer_data['product_id'],
                "quantity": transfer_data['quantity'],
                "destination_store": destination_store,
                "origin_store": origin_store.id,
            }

            try:
                transfer = ProductTransfer.objects.get(**data, transfer_datetime=None)
            except ProductTransfer.DoesNotExist:
                return Response(
                    {"status": "Transpaso no encontrado"}, status=status.HTTP_404_NOT_FOUND
                )
            transfers_to_update.append({'transfer': transfer, 'quantity': transfer_data['quantity']})



        for transfer_to_update in transfers_to_update:
            with transaction.atomic():  # Comienza una transacción

                transfer = transfer_to_update['transfer']

                # Actualiza la fecha y hora del traspaso
                transfer.transfer_datetime = datetime.now()
                transfer.save()

                # Actualiza el stock en la tienda de destino
                destination_store = transfer.destination_store

                store_product_destination_data = {"product": transfer.product, "store": transfer.destination_store}
                store_product_origin_data = {"product": transfer.product, "store": transfer.origin_store}
                
                store_product_destination_data = StoreProduct.objects.get(**store_product_destination_data)
                store_product_destination_data.stock += transfer_to_update['quantity']
                store_product_destination_data.save()

                # Verifica y actualiza el stock en la tienda de origen
                store_product_origin_data = StoreProduct.objects.get(**store_product_origin_data)
                store_product_origin_data.stock -= transfer_to_update['quantity']
                store_product_origin_data.save()

        return Response(
            {"status": "Traspaso confirmado"}, status=status.HTTP_200_OK
        )


class BrandViewSet(viewsets.ModelViewSet):
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()