from products.decorators import get_store
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import StoreProductLog
from .serializers import StoreProductLogSerializer, StoreProductLogSerializer2
from rest_framework import viewsets

# Create your views here.
@method_decorator(get_store(), name="dispatch")
class StoreProductLogsView(APIView):
	@transaction.atomic  # Decorador para asegurar la atomicidad de todo el método
	def get(self, request):
		store_product_id = request.GET.get("store-product-id")
		date = request.GET.get("date")
		brand_id = request.GET.get("brand_id")
		action = request.GET.get("action")
		store = request.store
		store_related = request.GET.get("store_related")

		if store_product_id:
			store_product_logs = StoreProductLog.objects.filter(
				store_product__id=store_product_id
			).order_by("-id")
			serializer_class = StoreProductLogSerializer
		else:
			q = {"store_product__store": store}
			if date:
				q["created_at__date"] = date
			if brand_id:
				q["store_product__product__brand__id"] = brand_id

			if action:
				q["action"] = action

			if store_related:
				q["store_related"] = store_related

			store_product_logs = StoreProductLog.objects.filter(**q).order_by("-id")
			serializer_class = StoreProductLogSerializer2

		serializer = serializer_class(store_product_logs, many=True)
		return Response(serializer.data, status=status.HTTP_200_OK)


class StoreProductLogsChoicesView(APIView):
	def get(self, request):
		choices = [
			{"value": key, "label": label}
			for key, label in StoreProductLog.ACTIONS_CHOICES
		]
		return Response(choices)
	

class StoreProductLogViewSet(viewsets.ModelViewSet):
    serializer_class = StoreProductLogSerializer

    def get_queryset(self):
        return StoreProductLog.objects.all()