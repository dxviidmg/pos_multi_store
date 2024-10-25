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
        
        # Intentar obtener la tienda, manejar la excepción si no existe
        try:
            store = Store.objects.get(manager=self.request.user)
        except Store.DoesNotExist:
            return StoreProduct.objects.none()  # Retornar un queryset vacío si la tienda no existe

        # Construir la consulta de búsqueda si se proporciona un término
        if q:
            search_fields = ['brand__name', 'category__name', 'code', 'name']
            query = reduce(or_, (Q(**{f"{field}__icontains": q}) for field in search_fields))
            product_queryset = Product.objects.filter(query).select_related('brand', 'category')[:3]
        else:
            product_queryset = Product.objects.all().select_related('brand', 'category')[:3]

        # Filtrar los productos de la tienda de forma eficiente
        return StoreProduct.objects.filter(product__in=product_queryset, store=store).prefetch_related('product')

