from rest_framework import serializers
from .models import SpecialClient, SpecialClientType


class SpecialClientTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialClientType
        fields = "__all__"

class SpecialClientSerializer(serializers.ModelSerializer):
    special_client_type = SpecialClientTypeSerializer()


    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return obj.get_full_name()

    class Meta:
        model = SpecialClient
        fields = "__all__"