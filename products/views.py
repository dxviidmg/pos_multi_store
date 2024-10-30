from rest_framework import viewsets
from .serializers import StoreProductSerializer
from .models import StoreProduct, Product, Store
from django.db.models import Q
from functools import reduce
from operator import or_


class StoreProductViewSet(viewsets.ModelViewSet):
    serializer_class = StoreProductSerializer

    def get_queryset(self):
        q = self.request.GET.get("q", "")
        code = self.request.GET.get("code", "")
        
        # Intentar obtener la tienda, retornar un queryset vacío si no existe
        try:
            store = Store.objects.get(manager=self.request.user)
        except Store.DoesNotExist:
            return StoreProduct.objects.none()

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

