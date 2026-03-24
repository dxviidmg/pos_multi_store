from django.shortcuts import render
from rest_framework import viewsets

from .models import StorePrinter
from .serializers import StorePrinterSerializer

# Create your views here.
class StorePrinterViewSet(viewsets.ModelViewSet):
	serializer_class = StorePrinterSerializer

	def get_queryset(self):
		tenant = self.request.user.get_tenant()
		return StorePrinter.objects.filter(store__tenant=tenant)