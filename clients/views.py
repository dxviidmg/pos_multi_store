from rest_framework import viewsets
from .serializers import ClientSerializer
from .models import Client
from django.db.models import Q
from functools import reduce
from operator import or_


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer

    def get_queryset(self):
        q = self.request.GET.get("q")

        if q:
            search_fields = ['first_name', 'last_name', 'phone_number']
            query = reduce(or_, (Q(**{f"{field}__icontains": q}) for field in search_fields))
            return Client.objects.filter(query)
        return Client.objects.all()