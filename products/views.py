from rest_framework import viewsets
from .serializers import StoreProductSerializer, ProductTransferSerializer, StoreSerializer
from .models import StoreProduct, Product, Store, ProductTransfer
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
            return StoreProduct.objects.filter(product=product, store=store) if product else StoreProduct.objects.none()

        # Construir la consulta de búsqueda en `Product` si se proporciona `q`
        filters = Q()
        if q:
            filters |= Q(brand__name__icontains=q) | Q(code__icontains=q) | Q(name__icontains=q)
        
        # Obtener productos y filtrar `StoreProduct` según la tienda
        product_queryset = Product.objects.filter(filters).select_related("brand")[:5]
        return StoreProduct.objects.filter(product__in=product_queryset, store=store).prefetch_related("product")




class ProductTransferViewSet(viewsets.ModelViewSet):
    serializer_class = ProductTransferSerializer

    def get_queryset(self):
        store = self.request.user.get_store()

        return ProductTransfer.objects.filter(Q(origin_store=store) | Q(destination_store=store), transfer_datetime=None)



class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = StoreSerializer
    queryset = Store.objects.all()
    def get_queryset(self):
        store = self.request.user.get_store()

        return Store.objects.exclude(id=store.id)




class ConfirmProductTransfer(APIView):
    def post(self, request):
        product = request.data.get("product")
        quantity = request.data.get("quantity")
        destination_store = request.data.get("destination_store")

        origin_store = self.request.user.get_store()

        data = {"product": product, "quantity": quantity, "destination_store": destination_store, 'origin_store': origin_store.id}
        data2 = {"product": product, "store": destination_store}
        data3 = {"product": product, "store": origin_store}
        print('data', data)
        try:
            transfer = ProductTransfer.objects.get(**data, transfer_datetime=None)
        except ProductTransfer.DoesNotExist:
            print('aqui')
            return Response({"status": "Transpaso no encontrado"}, status=status.HTTP_404_NOT_FOUND)            
        

        try:
            with transaction.atomic():  # Comienza una transacción
                # Verifica si el traspaso existe
                transfer = ProductTransfer.objects.get(
                    product=product, 
                    origin_store=origin_store, 
                    destination_store=destination_store, 
                    transfer_datetime=None
                )

                # Actualiza la fecha y hora del traspaso
                transfer.transfer_datetime = datetime.now()
                transfer.save()

                # Actualiza el stock en la tienda de destino
                store_product_destination = StoreProduct.objects.get(product=product, store=destination_store)
                store_product_destination.stock += quantity
                store_product_destination.save()

                # Verifica y actualiza el stock en la tienda de origen
                store_product_origin = StoreProduct.objects.get(product=product, store=origin_store)
                if store_product_origin.stock < quantity:
                    return Response({"status": "Stock insuficiente en la tienda de origen"}, status=status.HTTP_400_BAD_REQUEST)
                
                store_product_origin.stock -= quantity
                store_product_origin.save()

            return Response({'status': 'Traspaso confirmado'}, status=status.HTTP_200_OK)

        except ProductTransfer.DoesNotExist:
            return Response({"status": "Traspaso no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        except StoreProduct.DoesNotExist:
            return Response({"status": "Producto o tienda no encontrados"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": "Error al confirmar el traspaso", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

