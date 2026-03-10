from rest_framework import viewsets, mixins
from .serializers import PaymentSerializer, TenantSerializer
from .models import Payment, Tenant
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


class TenantViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = TenantSerializer
    
    def get_object(self):
        return self.request.user.get_tenant()


class TenantInfoView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        
        if tenant.is_sandbox:
            notices = [{"notice": "Soy una cuenta de demostración", "variant": "success"}]
        else:
            notices = []
            payment = Payment.objects.filter(tenant=tenant).only('end_of_validity').last()
            
            if not payment:
                notices.append({"notice": "No existe ningún pago, favor de pagar", "variant": "error"})
            else:
                days_diff = (payment.end_of_validity - date.today()).days
                if days_diff < 0:
                    notices.append({"notice": "Tiene un adeudo, favor de pagar", "variant": "error"})
                elif days_diff == 0:
                    notices.append({"notice": "Ultimo dia de pago, favor de pagar", "variant": "warning"})
                elif days_diff <= 5:
                    notices.append({"notice": f"Próximo pago en {days_diff} días", "variant": "alert"})

        return Response({
            "notices": notices,
            "product_count": tenant.count_products(),
        })
    


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