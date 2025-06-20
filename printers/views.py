from django.shortcuts import render
from .models import StorePrinter
from .serializers import StorePrinterSerializer
from rest_framework import viewsets

# Create your views here.
class StorePrinterViewSet(viewsets.ModelViewSet):
	serializer_class = StorePrinterSerializer

	def get_queryset(self):
		tenant = self.request.user.get_tenant()
		return StorePrinter.objects.filter(store__tenant=tenant)