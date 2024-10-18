from rest_framework import viewsets
from .serializers import SpecialClientSerializer
from .models import SpecialClient
from django.db.models import Q
from functools import reduce
from operator import or_


class SpecialClientViewSet(viewsets.ModelViewSet):
    serializer_class = SpecialClientSerializer

    def get_queryset(self):
        q = self.request.GET.get("q")

        if q:
            search_fields = ['first_name', 'last_name', 'phone_number']
            query = reduce(or_, (Q(**{f"{field}__icontains": q}) for field in search_fields))
            return SpecialClient.objects.filter(query)
        return SpecialClient.objects.all()