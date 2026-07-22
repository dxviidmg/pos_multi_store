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
from pos_multi_store.permissions import HasAPIKey

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


class TenantExistsView(APIView):
    permission_classes = [HasAPIKey]
    authentication_classes = []

    def get(self, request):
        short_name = request.query_params.get('short_name', '').strip()
        if not short_name:
            return Response({"error": "short_name is required"}, status=400)
        exists = Tenant.objects.filter(short_name=short_name).exists()
        return Response({"exists": exists})


class PublicTenantCreateView(APIView):
    permission_classes = [HasAPIKey]
    authentication_classes = []

    def post(self, request):
        from django.contrib.auth.models import User
        from django.contrib.auth.hashers import make_password
        from django.db import transaction

        data = request.data

        # Validar campos requeridos
        required = ['name', 'short_name', 'first_name', 'last_name', 'email', 'plan_id', 'card_token', 'payer_email']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return Response(
                {"error": f"Campos requeridos: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        short_name = data['short_name'].strip().upper()

        # Verificar unicidad
        if Tenant.objects.filter(short_name=short_name).exists():
            return Response(
                {"error": "El código de negocio ya está en uso."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=data['email']).exists():
            return Response(
                {"error": "Ya existe una cuenta con este correo."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar plan
        try:
            plan = Plan.objects.get(id=data['plan_id'], billing_type="S")
        except Plan.DoesNotExist:
            return Response({"error": "Plan no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        if not plan.mp_plan_id:
            return Response(
                {"error": "Plan sin configuración de suscripción en Mercado Pago"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Procesar suscripción en Mercado Pago primero (antes de crear datos locales)
        mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
        payload = {
            "preapproval_plan_id": plan.mp_plan_id,
            "card_token_id": data['card_token'],
            "payer_email": data['payer_email'],
            "external_reference": short_name,
            "status": "authorized",
        }
        headers = {
            "Authorization": f"Bearer {mp_access_token}",
            "Content-Type": "application/json",
        }

        logger.info(f"[PublicTenantCreate] preapproval payload: {payload}")

        mp_response = requests.post(
            "https://api.mercadopago.com/preapproval",
            json=payload,
            headers=headers
        )

        logger.info(f"[PublicTenantCreate] preapproval response: {mp_response.status_code} - {mp_response.json()}")

        if mp_response.status_code not in [200, 201]:
            mp_data = mp_response.json()
            error_msg = mp_data.get("message", "Error al procesar el pago.")
            return Response(
                {"error": error_msg, "details": mp_data},
                status=status.HTTP_400_BAD_REQUEST
            )

        mp_data = mp_response.json()

        # Pago exitoso → crear tenant, owner y suscripción en transacción
        with transaction.atomic():
            username = f"{short_name}.propietario"
            owner = User.objects.create(
                username=username,
                first_name=data['first_name'],
                last_name=data['last_name'],
                email=data['email'],
                password=make_password(data.get('password', username)),
            )

            tenant = Tenant(
                name=data['name'],
                short_name=short_name,
                plan=plan,
            )
            # Tenant.save() usará get_or_create y encontrará el owner ya creado
            tenant.save()

            Subscription.objects.create(
                tenant=tenant,
                mp_subscription_id=mp_data["id"],
                card_token_id="",
                payer_email=data['payer_email'],
                payment_method_id=data.get('payment_method_id', 'credit_card'),
                status="active",
                amount=plan.price,
            )

        return Response({
            "id": tenant.id,
            "short_name": tenant.short_name,
            "username": owner.username,
            "mp_subscription_id": mp_data["id"],
        }, status=status.HTTP_201_CREATED)


class PublicPlansView(APIView):
    permission_classes = [HasAPIKey]
    authentication_classes = []

    def get(self, request):
        from .serializers import PlanSerializer
        plans = Plan.objects.filter(billing_type="S", is_sandbox=False)
        serializer = PlanSerializer(plans, many=True)
        return Response(serializer.data)


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
    """Crea suscripción recurrente en Mercado Pago via Preapproval."""

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

        if not plan.mp_plan_id:
            return Response(
                {"error": "Plan sin configuración de suscripción en Mercado Pago"},
                status=status.HTTP_400_BAD_REQUEST
            )

        tenant = request.user.get_tenant()
        mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN

        # Crear suscripción recurrente con Preapproval
        payload = {
            "preapproval_plan_id": plan.mp_plan_id,
            "card_token_id": card_token,
            "payer_email": payer_email,
            "external_reference": tenant.short_name,
            "status": "authorized",
        }

        headers = {
            "Authorization": f"Bearer {mp_access_token}",
            "Content-Type": "application/json",
        }

        logger.info(f"[CreateSubscription] preapproval payload: {payload}")

        response = requests.post(
            "https://api.mercadopago.com/preapproval",
            json=payload,
            headers=headers
        )

        logger.info(f"[CreateSubscription] preapproval response: {response.status_code} - {response.json()}")

        if response.status_code not in [200, 201]:
            return Response(
                {"error": "Error al crear suscripción", "details": response.json()},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = response.json()

        # Cancelar suscripciones anteriores del tenant en MP y localmente
        old_subs = Subscription.objects.filter(tenant=tenant, status="active")
        for old_sub in old_subs:
            try:
                requests.put(
                    f"https://api.mercadopago.com/preapproval/{old_sub.mp_subscription_id}",
                    json={"status": "cancelled"},
                    headers=headers
                )
            except Exception as e:
                logger.warning(f"[CreateSubscription] Error cancelling old sub {old_sub.mp_subscription_id}: {e}")
        old_subs.update(status="cancelled")

        subscription = Subscription.objects.create(
            tenant=tenant,
            mp_subscription_id=data["id"],
            card_token_id="",  # No se reutiliza, campo legacy
            payer_email=payer_email,
            payment_method_id=payment_method_id,
            status="active",
            amount=plan.price,
        )

        # Actualizar plan del tenant
        tenant.plan = plan
        tenant.save(update_fields=["plan"])

        return Response({
            "id": subscription.id,
            "mp_subscription_id": data["id"],
            "status": data.get("status"),
            "amount": float(plan.price),
        }, status=status.HTTP_201_CREATED)


class MPWebhookView(APIView):
    """Recibe notificaciones de Mercado Pago (pagos y suscripciones)."""
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info(f"[MPWebhook] received: {request.data} params: {request.query_params}")
        topic = request.data.get("type") or request.query_params.get("topic")
        data = request.data.get("data", {})

        if topic == "subscription_preapproval":
            return self._handle_subscription_update(data, request)
        elif topic == "payment":
            return self._handle_payment(data)

        logger.info(f"[MPWebhook] ignored: topic={topic}")
        return Response(status=status.HTTP_200_OK)

    def _handle_payment(self, data):
        """Procesa notificación de pago (manual o recurrente via preapproval)."""
        payment_id = data.get("id")
        if not payment_id:
            return Response(status=status.HTTP_200_OK)

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

        # Buscar tenant por external_reference (formato: short_name_MMYY o solo short_name)
        external_reference = mp_payment.get("external_reference", "")
        if not external_reference:
            logger.warning(f"[MPWebhook] payment without external_reference, payment_id={payment_id}")
            return Response(status=status.HTTP_200_OK)

        short_name = external_reference.split("_")[0]
        try:
            tenant = Tenant.objects.get(short_name=short_name)
        except Tenant.DoesNotExist:
            logger.warning(f"[MPWebhook] tenant not found for short_name={short_name} (external_reference={external_reference})")
            return Response(status=status.HTTP_200_OK)

        # Para pagos recurrentes de preapproval, generar external_reference único
        # MP usa el external_reference del preapproval (short_name), no incluye fecha
        if "_" not in external_reference:
            # Es un pago recurrente de preapproval, usar payment_id como referencia
            external_reference = f"{short_name}_{mp_payment.get('id')}"

        # Evitar duplicados
        if Payment.objects.filter(mp_external_reference=external_reference).exists():
            logger.info(f"[MPWebhook] duplicate external_reference={external_reference}, skipping")
            return Response(status=status.HTTP_200_OK)

        # Registrar pago
        Payment.objects.create(tenant=tenant, months=1, mp_external_reference=external_reference)
        logger.info(f"[MPWebhook] payment registered: tenant={tenant.short_name} amount={mp_payment.get('transaction_amount')}")

        return Response(status=status.HTTP_200_OK)

    def _handle_subscription_update(self, data, request):
        """Actualiza estado local de suscripción cuando MP notifica cambios."""
        sub_id = data.get("id") or request.query_params.get("id")
        if not sub_id:
            return Response(status=status.HTTP_200_OK)

        mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
        response = requests.get(
            f"https://api.mercadopago.com/preapproval/{sub_id}",
            headers={"Authorization": f"Bearer {mp_access_token}"},
        )
        if response.status_code != 200:
            logger.warning(f"[MPWebhook] preapproval query failed: {response.status_code}")
            return Response(status=status.HTTP_200_OK)

        mp_sub = response.json()
        new_status = mp_sub.get("status")
        logger.info(f"[MPWebhook] subscription update: id={sub_id} status={new_status}")

        status_map = {
            "authorized": "active",
            "paused": "paused",
            "cancelled": "cancelled",
        }

        try:
            subscription = Subscription.objects.get(mp_subscription_id=str(sub_id))
            subscription.status = status_map.get(new_status, subscription.status)
            subscription.save(update_fields=["status"])
            logger.info(f"[MPWebhook] subscription {sub_id} updated to {subscription.status}")
        except Subscription.DoesNotExist:
            logger.warning(f"[MPWebhook] subscription not found: mp_subscription_id={sub_id}")

        return Response(status=status.HTTP_200_OK)
