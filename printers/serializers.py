from rest_framework import serializers
from .models import StorePrinter, Printer
from products.serializers import StoreSerializer

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