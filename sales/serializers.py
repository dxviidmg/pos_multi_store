from rest_framework import serializers
from .models import Sale
from clients.serializers import ClientSerializer

class SaleSerializer(serializers.ModelSerializer):
    client = ClientSerializer()

    class Meta:
        model = Sale
        fields = "__all__"


class SaleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = ["total", "client"]
#        fields = ["total"]


