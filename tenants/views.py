from rest_framework import viewsets
from .serializers import PaymentSerializer
from .models import Payment
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import date

# Create your views here.
class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        return Payment.objects.filter(tenant=tenant).order_by('id')
    


class TenantNoticesView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        today = date.today()

        payment = Payment.objects.filter(tenant=tenant).last()
        data = ["Soy un demo"] if tenant.is_sandbox else []

        if not tenant.is_sandbox:
            if not payment:
                data.append("No existe ningún pago")
            else:
                days_diff = (payment.end_of_validity - today).days
                if days_diff < 0:
                    data.append(f"Tiene un adeudo de {abs(days_diff)} días")
                elif days_diff <= 7:
                    data.append(f"Próximo pago en {days_diff} días")

        return Response(data, status=status.HTTP_200_OK)