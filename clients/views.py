from rest_framework import viewsets
from .serializers import ClientSerializer, DiscountSerializer
from .models import Client, Discount
from django.db.models import Q, Value
from django.db.models.functions import Concat


class DiscountViewSet(viewsets.ModelViewSet):
	serializer_class = DiscountSerializer

	def get_queryset(self):
		tenant = self.request.user.get_tenant()
		return Discount.objects.filter(tenant=tenant).order_by("discount_percentage")

	def perform_create(self, serializer):
		tenant = self.request.user.get_tenant()
		discount_instance = serializer.save(tenant=tenant)
		return discount_instance


class ClientViewSet(viewsets.ModelViewSet):
	serializer_class = ClientSerializer

	def get_queryset(self):
		q = self.request.GET.get("q")
		tenant = self.request.user.get_tenant()
		discounts = Discount.objects.filter(tenant=tenant).order_by(
			"discount_percentage"
		)
		if q:
			# Anotar `full_name` y filtrar en una sola línea
			return Client.objects.annotate(
				full_name=Concat("first_name", Value(" "), "last_name")
			).filter(
				Q(phone_number__icontains=q) | Q(full_name__icontains=q),
				discount__in=discounts,
			)
		return Client.objects.filter(discount__in=discounts)
