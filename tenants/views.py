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

from .models import MONTHY_PRICE_BY_STORE, Payment, Plan, Subscription, SubscriptionPayment, Tenant
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
        
        if tenant.is_sandbox:
            notices = [{"notice": "Soy una cuenta de demostración", "variant": "success"}]
        else:
            notices = []
            payment = Payment.objects.filter(tenant=tenant).only('end_of_validity').last()
            
            if not payment:
                notices.append({"notice": "No se encontró un pago activo. Regularice su cuenta para continuar.", "variant": "error"})
            else:
                days_diff = (payment.end_of_validity - date.today()).days
                if days_diff < 0:
                    notices.append({"notice": "Su periodo de servicio ha vencido. Renueve para mantener el acceso.", "variant": "error"})
                elif days_diff == 0:
                    notices.append({"notice": "Su periodo de servicio vence hoy. Renueve para evitar interrupciones.", "variant": "warning"})
                elif days_diff <= 5:
                    notices.append({"notice": f"Su periodo de servicio vence en {days_diff} días.", "variant": "warning"})

        return Response({
            "notices": notices,
            "product_count": tenant.count_products(),
        })
    


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
    """Crea una suscripción en Mercado Pago con plan asociado."""

    def post(self, request):
        plan_id = request.data.get("plan_id")
        card_token_id = request.data.get("card_token_id")
        payer_email = request.data.get("payer_email")

        if not all([plan_id, card_token_id, payer_email]):
            return Response(
                {"error": "plan_id, card_token_id y payer_email son requeridos"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar que el usuario es owner
        if request.user.get_role() != 'owner':
            return Response(
                {"error": "Solo los propietarios pueden crear suscripciones"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            plan = Plan.objects.get(id=plan_id)
        except Plan.DoesNotExist:
            return Response({"error": "Plan no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        if not plan.mp_plan_id:
            # Crear el plan en Mercado Pago automáticamente
            mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
            create_plan_payload = {
                "reason": plan.name,
                "auto_recurring": {
                    "frequency": 1,
                    "frequency_type": "months",
                    "transaction_amount": float(plan.price),
                    "currency_id": "MXN",
                },
                "back_url": settings.MERCADO_PAGO_BACK_URL,
            }
            create_plan_response = requests.post(
                "https://api.mercadopago.com/preapproval_plan",
                json=create_plan_payload,
                headers={
                    "Authorization": f"Bearer {mp_access_token}",
                    "Content-Type": "application/json",
                },
            )
            if create_plan_response.status_code not in [200, 201]:
                return Response(
                    {"error": "No se pudo crear el plan en Mercado Pago", "detail": create_plan_response.json()},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            plan.mp_plan_id = create_plan_response.json()["id"]
            plan.save(update_fields=["mp_plan_id"])

        tenant = request.user.get_tenant()

        # Crear suscripción en Mercado Pago
        mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
        base_ref = f"tenant-{tenant.short_name}-plan-{plan.name}".replace(" ", "-").lower()
        count = Subscription.objects.filter(external_reference__startswith=base_ref).count()
        external_reference = f"{base_ref}-{count + 1}"

        payload = {
            "preapproval_plan_id": plan.mp_plan_id,
            "card_token_id": card_token_id,
            "payer_email": payer_email,
            "status": "authorized",
            "external_reference": external_reference,
        }

        headers = {
            "Authorization": f"Bearer {mp_access_token}",
            "Content-Type": "application/json",
        }

        logger.info(f"[CreateSubscription] payload: {payload}")
        response = requests.post(
            "https://api.mercadopago.com/preapproval",
            json=payload,
            headers=headers
        )

        logger.info(f"[CreateSubscription] response: {response.status_code} - {response.json()}")

        if response.status_code not in [200, 201]:
            return Response(
                {"error": "Error al crear suscripción en Mercado Pago", "details": response.json()},
                status=status.HTTP_400_BAD_REQUEST
            )

        mp_data = response.json()

        # Crear registro local
        subscription = Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            mp_subscription_id=mp_data["id"],
            payer_email=payer_email,
            external_reference=external_reference,
            status=mp_data.get("status", "authorized"),
            next_payment_date=mp_data.get("next_payment_date", "")[:10] or None,
        )

        # Mover el plan del tenant a la suscripción
        tenant.plan = None
        tenant.save(update_fields=["plan"])

        return Response({
            "id": subscription.id,
            "status": subscription.status,
            "next_payment_date": subscription.next_payment_date,
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

        # Buscar suscripción por external_reference o preapproval_id
        external_reference = mp_payment.get("external_reference", "")
        preapproval_id = mp_payment.get("metadata", {}).get("preapproval_id", "")
        subscription = None
        if external_reference and external_reference != "Recurring payment validation":
            subscription = Subscription.objects.filter(external_reference=external_reference, status="authorized").first()
        if not subscription and preapproval_id:
            subscription = Subscription.objects.filter(mp_subscription_id=preapproval_id, status="authorized").first()
        if not subscription:
            logger.warning(f"[MPWebhook] subscription not found for ref={external_reference} preapproval={preapproval_id}")
            return Response(status=status.HTTP_200_OK)

        # Evitar duplicados
        if SubscriptionPayment.objects.filter(mp_payment_id=str(payment_id)).exists():
            logger.info(f"[MPWebhook] duplicate payment_id={payment_id}, skipping")
            return Response(status=status.HTTP_200_OK)

        # Registrar pago
        tenant = subscription.tenant
        payment = Payment.objects.create(tenant=tenant, months=1)
        SubscriptionPayment.objects.create(
            subscription=subscription,
            mp_payment_id=str(payment_id),
            amount=mp_payment.get("transaction_amount", payment.total),
            status="approved",
            paid_at=datetime.now(),
        )
        logger.info(f"[MPWebhook] payment registered: tenant={tenant.short_name} amount={mp_payment.get('transaction_amount')}")

        return Response(status=status.HTTP_200_OK)
