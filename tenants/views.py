from rest_framework import viewsets
from .serializers import PaymentSerializer
from .models import Payment
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import date
from .utils import render_redeploy

# Create your views here.
class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        return Payment.objects.filter(tenant=tenant).order_by("id")


class TenantInfoView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        today = date.today()

        payment = Payment.objects.filter(tenant=tenant).last()
        notices = ["Soy una cuenta de demostración"] if tenant.is_sandbox else []

        if not tenant.is_sandbox:
            if not payment:
                notices.append("No existe ningún pago, favor de pagar")
            else:
                days_diff = (payment.end_of_validity - today).days
                if days_diff < 0:
                    notices.append(f"Tiene un adeudo, favor de pagar")
                elif days_diff == 0:
                    notices.append(f"Ultimo dia de pago, favor de pagar")
                elif days_diff <= 7:
                    notices.append(f"Próximo pago en {days_diff} días")

        return Response(
            {
                "notices": notices,
                "product_count": tenant.count_products(),
                "supports_departments": tenant.supports_departments,
            },
            status=status.HTTP_200_OK,
        )
    


class RenderRedeployView(APIView):
    def get(self, request):
        result = render_redeploy()

        if not result.get("success"):
            return Response(
                data={
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                },
                status=result.get("status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            )

        return Response(
            data={
                "success": True,
                "deploy": result.get("data"),
            },
            status=status.HTTP_200_OK,
        )