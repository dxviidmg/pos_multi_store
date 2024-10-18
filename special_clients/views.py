from rest_framework import viewsets
from .serializers import SpecialClientSerializer
from .models import SpecialClient
from django.db.models import Q

class SpecialClientViewSet(viewsets.ModelViewSet):
    serializer_class = SpecialClientSerializer
#    authentication_classes = [TokenAuthentication]
#    permission_classes = [IsAuthenticated, IsACompany]

    def get_queryset(self):
        q = self.request.GET.get("q")

        if q:
            return SpecialClient.objects.filter(Q(first_name__contains=q) | Q(last_name__contains=q) | Q(phone_number__contains=q))
        return SpecialClient.objects.all()