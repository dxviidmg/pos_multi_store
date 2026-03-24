from rest_framework import serializers

from products.serializers import StoreSerializer
from .models import Printer, StorePrinter

class PrinterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Printer
        fields = "__all__"

class StorePrinterSerializer(serializers.ModelSerializer):
    store = StoreSerializer()
    printer = PrinterSerializer()

    class Meta:
        model = StorePrinter
        fields = "__all__"