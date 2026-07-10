import hmac
import hashlib
import logging
import requests
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

import mercadopago

from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment, Plan, Subscription, SubscriptionPayment, Tenant
from .serializers import PaymentSerializer, TenantSerializer
from .utils import render_redeploy

# Create your views here.
class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        tenant = self.request.user.get_tenant()
        return Payment.objects.filter(tenant=tenant).order_by("-id")


class TenantViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = TenantSerializer
    
    def get_object(self):
        return self.request.user.get_tenant()


class TenantInfoView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        show_mp_modal = False
        
        if tenant.is_sandbox:
            notices = [{"notice": "Soy una cuenta de demostración", "variant": "success"}]
            payment = Payment.objects.filter(tenant=tenant).only('end_of_validity').last()
            if not payment:
                show_mp_modal = True
            else:
                show_mp_modal = (payment.end_of_validity - date.today()).days < 5
        else:
            notices = []
            payment = Payment.objects.filter(tenant=tenant).only('end_of_validity').last()
            
            if not payment:
                notices.append({"notice": "No se encontró un pago activo. Regularice su cuenta para continuar.", "variant": "error"})
                show_mp_modal = True
            else:
                days_diff = (payment.end_of_validity - date.today()).days
                show_mp_modal = days_diff < 5
                if days_diff < 0:
                    notices.append({"notice": "Su periodo de servicio ha vencido. Renueve para mantener el acceso.", "variant": "error"})
                elif days_diff == 0:
                    notices.append({"notice": "Su periodo de servicio vence hoy. Renueve para evitar interrupciones.", "variant": "warning"})
                elif days_diff <= 5:
                    notices.append({"notice": f"Su periodo de servicio vence en {days_diff} días.", "variant": "warning"})

        return Response({
            "notices": notices,
            "product_count": tenant.count_products(),
            "show_mp_modal": show_mp_modal,
        })
    


class MercadoPagoPreferenceView(APIView):
    def post(self, request):
        tenant = request.user.get_tenant()
        plan = tenant.plan
        if not plan:
            return Response({"error": "No tiene un plan asignado."}, status=status.HTTP_400_BAD_REQUEST)

        last_payment = Payment.objects.filter(tenant=tenant).last()
        if last_payment:
            months_owed = max(1, (date.today().year - last_payment.end_of_validity.year) * 12
                             + date.today().month - last_payment.end_of_validity.month)
        else:
            months_owed = 1

        amount = float(plan.price * months_owed)

        from dateutil.relativedelta import relativedelta
        if last_payment:
            start = last_payment.end_of_validity + relativedelta(days=1)
        else:
            start = date.today()
        end = start + relativedelta(months=months_owed) - relativedelta(days=1)

        MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
        if months_owed == 1:
            title = f"SmartVenta - {MESES[start.month-1]} {start.year}"
        elif start.year == end.year:
            title = f"SmartVenta - {MESES[start.month-1]} {MESES[end.month-1]} {start.year}"
        else:
            title = f"SmartVenta - {MESES[start.month-1]} {start.year} - {MESES[end.month-1]} {end.year}"

        sdk = mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)
        preference_data = {
            "items": [{
                "title": title,
                "quantity": 1,
                "unit_price": amount,
                "currency_id": "MXN",
            }],
            "back_urls": {
                "success": settings.MERCADO_PAGO_BACK_URL,
                "failure": settings.MERCADO_PAGO_BACK_URL,
                "pending": settings.MERCADO_PAGO_BACK_URL,
            },
            "external_reference": f"{tenant.short_name}_{start.strftime('%m%y')}",
            "auto_return": "approved",
        }

        result = sdk.preference().create(preference_data)
        if result["status"] != 201:
            return Response({"error": result.get("response").get("message")}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"init_point": result["response"]["init_point"]})


class CreateProductsOnSaleView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        return Response({"create_products_on_sale": tenant.create_products_on_sale})


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



class CurrentPlanView(APIView):
    def get(self, request):
        # Verificar que el usuario es owner
        if request.user.get_role() != 'owner':
            return Response(
                {"error": "Solo los propietarios pueden ver la información del plan"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        tenant = request.user.get_tenant()
        plan = tenant.get_plan()
        
        if not plan:
            return Response({
                "has_plan": False,
                "message": "No hay un plan asignado"
            })
        
        return Response({
            "has_plan": True,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "price": str(plan.price),
                "stores": plan.stores,
                "billing_type": plan.billing_type,
                "billing_type_display": plan.get_billing_type_display()
            }
        })


class PlanEquivalentView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        current_plan = tenant.get_plan()
        try:
            plan = Plan.objects.get(stores=current_plan.stores, is_sandbox=current_plan.is_sandbox, billing_type="S")
        except Plan.DoesNotExist:
            return Response({"error": "No hay plan de suscripción para esta cantidad de tiendas"}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": plan.id,
            "name": plan.name,
            "price": str(plan.price),
            "stores": plan.stores,
        })


class CreateSubscriptionView(APIView):
    """Guarda token de tarjeta y realiza pago con /v1/payments."""

    def post(self, request):
        card_token = request.data.get("card_token")
        payer_email = request.data.get("payer_email")
        plan_id = request.data.get("plan_id")
        payment_method_id = request.data.get("payment_method_id", "credit_card")

        if not all([card_token, payer_email, plan_id]):
            return Response(
                {"error": "card_token, payer_email y plan_id son requeridos"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.user.get_role() != 'owner':
            return Response(
                {"error": "Solo los propietarios pueden crear suscripciones"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            plan = Plan.objects.get(id=plan_id)
        except Plan.DoesNotExist:
            return Response({"error": "Plan no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        tenant = request.user.get_tenant()
        mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN

        # Pago con /v1/payments
        payment_payload = {
            "token": card_token,
            "installments": 1,
            "transaction_amount": float(plan.price),
            "payment_method_id": payment_method_id,
            "payer": {"email": payer_email},
            "description": f"Pago plan: {plan.name}",
        }

        headers = {
            "Authorization": f"Bearer {mp_access_token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": f"{tenant.short_name}_{plan_id}_{card_token}",
        }

        logger.info(f"[CreateSubscription] payment payload: {payment_payload}")

        payment_response = requests.post(
            "https://api.mercadopago.com/v1/payments",
            json=payment_payload,
            headers=headers
        )

        logger.info(f"[CreateSubscription] payment response: {payment_response.status_code} - {payment_response.json()}")

        if payment_response.status_code not in [200, 201]:
            return Response(
                {"error": "Error al procesar pago", "details": payment_response.json()},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment_data = payment_response.json()

        # Guardar token en suscripción para futuros cobros por cron
        subscription, created = Subscription.objects.update_or_create(
            tenant=tenant,
            defaults={
                "card_token_id": card_token,
                "payer_email": payer_email,
                "payment_method_id": payment_method_id,
                "mp_subscription_id": str(payment_data.get("id")),
                "status": "authorized",
            }
        )

        # Registrar pago y extender vigencia
        Payment.objects.create(tenant=tenant, months=1)

        # Actualizar plan del tenant
        tenant.plan = plan
        tenant.save(update_fields=["plan"])

        return Response({
            "id": subscription.id,
            "payment_id": payment_data.get("id"),
            "status": payment_data.get("status"),
            "amount": float(plan.price),
        }, status=status.HTTP_201_CREATED)


class MPWebhookView(APIView):
    """Recibe notificaciones de pago de Mercado Pago."""
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info(f"[MPWebhook] received: {request.data} params: {request.query_params}")
        topic = request.data.get("type") or request.query_params.get("topic")
        data = request.data.get("data", {})
        payment_id = data.get("id") or request.query_params.get("id")

        if topic != "payment" or not payment_id:
            logger.info(f"[MPWebhook] ignored: topic={topic}, payment_id={payment_id}")
            return Response(status=status.HTTP_200_OK)

        # Consultar pago en MP
        mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
        response = requests.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {mp_access_token}"},
        )
        if response.status_code != 200:
            logger.warning(f"[MPWebhook] MP payment query failed: {response.status_code}")
            return Response(status=status.HTTP_200_OK)

        mp_payment = response.json()
        logger.info(f"[MPWebhook] payment status={mp_payment.get('status')} ref={mp_payment.get('external_reference')} amount={mp_payment.get('transaction_amount')}")
        if mp_payment.get("status") != "approved":
            return Response(status=status.HTTP_200_OK)

        # Buscar tenant por external_reference (formato: short_name_MMYY)
        external_reference = mp_payment.get("external_reference", "")
        if not external_reference:
            logger.warning(f"[MPWebhook] payment without external_reference, payment_id={payment_id}")
            return Response(status=status.HTTP_200_OK)

        short_name = external_reference.split("_")[0]
        try:
            tenant = Tenant.objects.get(short_name=short_name)
        except Tenant.DoesNotExist:
            tenant = None
        if not tenant:
            logger.warning(f"[MPWebhook] tenant not found for short_name={short_name} (external_reference={external_reference})")
            return Response(status=status.HTTP_200_OK)

        # Evitar duplicados
        if Payment.objects.filter(mp_external_reference=external_reference).exists():
            logger.info(f"[MPWebhook] duplicate external_reference={external_reference}, skipping")
            return Response(status=status.HTTP_200_OK)

        # Registrar pago
        Payment.objects.create(tenant=tenant, months=1, mp_external_reference=external_reference)
        logger.info(f"[MPWebhook] payment registered: tenant={tenant.short_name} amount={mp_payment.get('transaction_amount')}")

        return Response(status=status.HTTP_200_OK)
