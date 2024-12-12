from rest_framework import viewsets
from .serializers import ClientSerializer, DiscountSerializer
from .models import Client, Discount
from django.db.models import Q, Value
from django.db.models.functions import Concat


class ClientViewSet(viewsets.ModelViewSet):
	serializer_class = ClientSerializer
	
	def get_queryset(self):
		q = self.request.GET.get("q")

		if q:
			# Anotar `full_name` y filtrar en una sola línea
			return Client.objects.annotate(
				full_name=Concat('first_name', Value(' '), 'last_name')
			).filter(
				Q(phone_number__icontains=q) | Q(full_name__icontains=q)
			)
		
		return Client.objects.all()


class DiscountViewSet(viewsets.ModelViewSet):
	serializer_class = DiscountSerializer

	def get_queryset(self):
		return Discount.objects.all().order_by('discount_percentage')
		