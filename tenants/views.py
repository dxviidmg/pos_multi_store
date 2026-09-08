import hmac
import hashlib
import logging
import requests
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

import mercadopago

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment, Plan, Subscription, SubscriptionPayment, Tenant
from .serializers import PaymentSerializer, SubscriptionSerializer, TenantSerializer
from .utils import render_redeploy
from pos_multi_store.permissions import HasAPIKey
from core.services.email import email_service

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
            # Crear plan en Mercado Pago automáticamente
            mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
            plan_payload = {
                "reason": f"SmartVenta - {plan.name}",
                "auto_recurring": {
                    "frequency": 1,
                    "frequency_type": "months",
                    "transaction_amount": float(plan.price),
                    "currency_id": "MXN",
                },
                "back_url": settings.MERCADO_PAGO_BACK_URL,
            }
            plan_headers = {
                "Authorization": f"Bearer {mp_access_token}",
                "Content-Type": "application/json",
            }
            logger.info(f"[PublicTenantCreate] Creando plan en MP: {plan_payload}")
            mp_plan_response = requests.post(
                "https://api.mercadopago.com/preapproval_plan",
                json=plan_payload,
                headers=plan_headers,
            )
            logger.info(f"[PublicTenantCreate] MP plan response: {mp_plan_response.status_code} - {mp_plan_response.json()}")

            if mp_plan_response.status_code not in [200, 201]:
                return Response(
                    {"error": "No se pudo crear el plan en Mercado Pago", "details": mp_plan_response.json()},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            plan.mp_plan_id = mp_plan_response.json()["id"]
            plan.save(update_fields=["mp_plan_id"])

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
            raw_password = data.get('password', username)
            owner = User.objects.create(
                username=username,
                first_name=data['first_name'],
                last_name=data['last_name'],
                email=data['email'],
                password=make_password(raw_password),
            )

            tenant = Tenant(
                name=data['name'],
                short_name=short_name,
                plan=plan,
            )
            # Tenant.save() usará get_or_create y encontrará el owner ya creado
            tenant.save()

            subscription = Subscription.objects.create(
                tenant=tenant,
                mp_subscription_id=mp_data["id"],
                card_token_id="",
                payer_email=data['payer_email'],
                payment_method_id=data.get('payment_method_id', 'credit_card'),
                status="authorized",
                amount=plan.price,
            )

        # Correo de bienvenida con credenciales (fuera de la transacción para
        # que un fallo de envío no revierta el alta del tenant)
        email_service.send_welcome_email(
            user_email=owner.email,
            username=owner.username,
            password=raw_password,
        )

        # Notificación interna a soporte: nuevo negocio registrado.
        email_service.notify_new_tenant(tenant, subscription=subscription, plan=plan)

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
        plans = Plan.objects.filter(billing_type="S", is_sandbox=False).order_by('stores')
        serializer = PlanSerializer(plans, many=True)
        return Response(serializer.data)


class TenantInfoView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        show_mp_modal = False
        notices = []
        payment = Payment.objects.filter(tenant=tenant).only('end_of_validity').last()
        active_subscription = Subscription.objects.filter(tenant=tenant, status="authorized").exists()

        if tenant.is_sandbox:
            notices = [{"notice": "Soy una cuenta de demostración", "variant": "success"}]
            if not payment:
                show_mp_modal = True
            else:
                show_mp_modal = (payment.end_of_validity - date.today()).days < 5
        elif active_subscription:
            # Tiene domiciliación activa: no mostrar modal de pago
            show_mp_modal = False
            if payment:
                days_diff = (payment.end_of_validity - date.today()).days
                if days_diff <= 5:
                    notices.append({
                        "notice": f"En próximos días se realizará el cobro automático de su suscripción. Asegúrese de tener saldo suficiente en su tarjeta para continuar usando el servicio.",
                        "variant": "warning"
                    })
        else:
            # Sin domiciliación: flujo manual
            if not payment:
                notices.append({"notice": "No se encontró un pago activo. Regularice su cuenta.", "variant": "error"})
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



class CanCreateStoreView(APIView):
    def get(self, request):
        tenant = request.user.get_tenant()
        plan = tenant.get_plan()

        if not plan:
            return Response({"can_create": False})

        from products.models import Store
        current_stores = Store.objects.filter(tenant=tenant).count()

        return Response({"can_create": current_stores < plan.stores})


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

        # Estado de negocio (3 valores derivados) y fecha de acceso.
        subscription_status = tenant.subscription_status()
        access_until = tenant.access_until()
        access_until_iso = (
            timezone.make_aware(
                datetime.combine(access_until, datetime.min.time())
            ).isoformat()
            if access_until else None
        )
        current_card = tenant.current_card()

        if not plan:
            return Response({
                "has_plan": False,
                "message": "No hay un plan asignado",
                "subscription_status": subscription_status,
                "access_until": access_until_iso,
                "current_card": current_card,
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
            },
            "subscription_status": subscription_status,
            "access_until": access_until_iso,
            "current_card": current_card,
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


class SubscriptionView(APIView):
    """Retorna las suscripciones del tenant."""

    def get(self, request):
        tenant = request.user.get_tenant()
        subscriptions = Subscription.objects.filter(tenant=tenant).order_by('-created_at')
        serializer = SubscriptionSerializer(subscriptions, many=True)
        return Response(serializer.data)


class TenantDatesView(APIView):
    """Retorna fechas clave del tenant: creación, domiciliación activa y primer pago."""

    def get(self, request):
        tenant = request.user.get_tenant()

        # Fecha de creación del tenant
        tenant_created = tenant.created_at

        # Fecha de la domiciliación (suscripción) activa
        active_subscription = Subscription.objects.filter(
            tenant=tenant, status="authorized"
        ).order_by('-created_at').first()

        subscription_date = active_subscription.created_at if active_subscription else None

        # Fecha del primer pago
        first_payment = Payment.objects.filter(
            tenant=tenant
        ).order_by('created_at').first()

        first_payment_date = first_payment.created_at if first_payment else None

        return Response({
            "tenant_created_at": tenant_created,
            "active_subscription_date": subscription_date,
            "first_payment_date": first_payment_date,
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
            # Crear plan en Mercado Pago automáticamente
            mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
            plan_payload = {
                "reason": f"SmartVenta - {plan.name}",
                "auto_recurring": {
                    "frequency": 1,
                    "frequency_type": "months",
                    "transaction_amount": float(plan.price),
                    "currency_id": "MXN",
                },
                "back_url": settings.MERCADO_PAGO_BACK_URL,
            }
            plan_headers = {
                "Authorization": f"Bearer {mp_access_token}",
                "Content-Type": "application/json",
            }
            logger.info(f"[CreateSubscription] Creando plan en MP: {plan_payload}")
            mp_plan_response = requests.post(
                "https://api.mercadopago.com/preapproval_plan",
                json=plan_payload,
                headers=plan_headers,
            )
            logger.info(f"[CreateSubscription] MP plan response: {mp_plan_response.status_code} - {mp_plan_response.json()}")

            if mp_plan_response.status_code not in [200, 201]:
                return Response(
                    {"error": "No se pudo crear el plan en Mercado Pago", "details": mp_plan_response.json()},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            plan.mp_plan_id = mp_plan_response.json()["id"]
            plan.save(update_fields=["mp_plan_id"])

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
        old_subs = Subscription.objects.filter(tenant=tenant, status="authorized")
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
            status="authorized",
            amount=plan.price,
        )

        # Reactivación: al crear una nueva suscripción se limpia el estado de
        # cancelación de negocio (sin historial, por decisión de diseño).
        tenant.cancelled_at = None
        tenant.cancellation_reason = ""
        tenant.plan = plan
        tenant.save(update_fields=["plan", "cancelled_at", "cancellation_reason"])

        return Response({
            "id": subscription.id,
            "mp_subscription_id": data["id"],
            "status": data.get("status"),
            "amount": float(plan.price),
        }, status=status.HTTP_201_CREATED)


class SubscriptionCancelView(APIView):
    """Cancela la suscripción del tenant (a nivel MP y a nivel negocio)."""

    def post(self, request):
        # Solo el owner puede cancelar (aunque el tenant tenga varios managers).
        if request.user.get_role() != 'owner':
            return Response(
                {"detail": "Solo el propietario puede cancelar la suscripción"},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant = request.user.get_tenant()

        # Idempotencia: si ya está cancelado a nivel negocio -> 409.
        if tenant.cancelled_at is not None:
            return Response(
                {"detail": "La suscripción ya está cancelada"},
                status=status.HTTP_409_CONFLICT,
            )

        # Validar motivo contra el enum permitido.
        reason = request.data.get("reason")
        valid_reasons = {c[0] for c in Tenant.CANCELLATION_REASON_CHOICES}
        if reason not in valid_reasons:
            return Response(
                {"detail": "reason inválido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Obtener la última suscripción activa (authorized) del tenant.
        subscription = (
            Subscription.objects.filter(tenant=tenant, status="authorized")
            .order_by("-created_at")
            .first()
        )
        if not subscription:
            return Response(
                {"detail": "No hay una suscripción activa"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Cancelar el preapproval en Mercado Pago (paso irreversible: va primero).
        mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
        try:
            mp_response = requests.put(
                f"https://api.mercadopago.com/preapproval/{subscription.mp_subscription_id}",
                json={"status": "cancelled"},
                headers={
                    "Authorization": f"Bearer {mp_access_token}",
                    "Content-Type": "application/json",
                },
            )
        except Exception as e:
            logger.error(f"[SubscriptionCancel] MP request error: {e}")
            return Response(
                {"detail": "No se pudo cancelar la suscripción. Contacta a soporte técnico."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if mp_response.status_code not in (200, 201):
            logger.error(
                f"[SubscriptionCancel] MP cancel failed: {mp_response.status_code} - {mp_response.text}"
            )
            return Response(
                {"detail": "No se pudo cancelar la suscripción. Contacta a soporte técnico."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Guardado local atómico: Subscription (MP) + Tenant (negocio) juntos.
        with transaction.atomic():
            subscription.status = "cancelled"
            subscription.save(update_fields=["status"])
            tenant.cancelled_at = timezone.now()
            tenant.cancellation_reason = reason
            tenant.save(update_fields=["cancelled_at", "cancellation_reason"])

        access_until = tenant.access_until()
        access_until_iso = (
            timezone.make_aware(
                datetime.combine(access_until, datetime.min.time())
            ).isoformat()
            if access_until else None
        )

        logger.info(
            f"[SubscriptionCancel] tenant={tenant.short_name} cancelled reason={reason}"
        )
        return Response(
            {"status": "cancelled", "access_until": access_until_iso},
            status=status.HTTP_200_OK,
        )


class SubscriptionUpdateCardView(APIView):
    """
    Escenario 1 (preventivo): el owner cambia la tarjeta antes de que falle el
    cobro. Actualiza el preapproval en MP con el nuevo card_token, SIN cancelar
    ni recrear la suscripción.
    """

    def post(self, request):
        if request.user.get_role() != 'owner':
            return Response(
                {"detail": "Solo el propietario puede actualizar la tarjeta"},
                status=status.HTTP_403_FORBIDDEN,
            )

        card_token = request.data.get("card_token")
        if not card_token:
            return Response(
                {"detail": "card_token es requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = request.user.get_tenant()
        subscription = (
            Subscription.objects.filter(tenant=tenant, status="authorized")
            .order_by("-created_at")
            .first()
        )
        if not subscription:
            return Response(
                {"detail": "No hay una suscripción activa"},
                status=status.HTTP_404_NOT_FOUND,
            )

        mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
        payload = {"card_token_id": card_token}
        payment_method_id = request.data.get("payment_method_id")
        if payment_method_id:
            payload["payment_method_id"] = payment_method_id

        try:
            mp_response = requests.put(
                f"https://api.mercadopago.com/preapproval/{subscription.mp_subscription_id}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {mp_access_token}",
                    "Content-Type": "application/json",
                },
            )
        except Exception as e:
            logger.error(f"[SubscriptionUpdateCard] MP request error: {e}")
            return Response(
                {"detail": "No se pudo actualizar la tarjeta. Contacta a soporte técnico."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if mp_response.status_code not in (200, 201):
            logger.error(
                f"[SubscriptionUpdateCard] MP update failed: {mp_response.status_code} - {mp_response.text}"
            )
            return Response(
                {"detail": "No se pudo actualizar la tarjeta. Contacta a soporte técnico."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            f"[SubscriptionUpdateCard] tenant={tenant.short_name} card updated on sub {subscription.mp_subscription_id}"
        )
        # Los datos de la nueva tarjeta se actualizarán al llegar el webhook del
        # próximo pago. Respondemos con los datos actuales conocidos.
        return Response(
            {"status": "authorized", "card_last_four": subscription.card_last_four},
            status=status.HTTP_200_OK,
        )


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

        # Localizar tenant por external_reference (short_name).
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

        pay_status = mp_payment.get("status")

        # --- Pago RECHAZADO: avisar al cliente (tarjeta vencida vs otro error) ---
        if pay_status == "rejected":
            self._handle_rejected_payment(mp_payment, tenant)
            return Response(status=status.HTTP_200_OK)

        if pay_status != "approved":
            # pending / in_process / etc.: no registrar aún.
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

        # Guardar datos NO sensibles de la tarjeta en la suscripción (historial).
        self._store_card_data(mp_payment)

        # ¿Es el primer pago de este tenant? (antes de registrar el nuevo)
        is_first_payment = not Payment.objects.filter(tenant=tenant).exists()

        # Registrar pago
        Payment.objects.create(tenant=tenant, months=1, mp_external_reference=external_reference)
        logger.info(f"[MPWebhook] payment registered: tenant={tenant.short_name} amount={mp_payment.get('transaction_amount')}")

        poi = mp_payment.get("point_of_interaction") or {}
        tx = poi.get("transaction_data") or {}
        sub = Subscription.objects.filter(
            mp_subscription_id=str(tx.get("subscription_id"))
        ).first()

        # Notificación interna a soporte solo en el primer pago.
        if is_first_payment:
            email_service.notify_first_payment(
                tenant,
                amount=mp_payment.get("transaction_amount"),
                payment_id=mp_payment.get("id"),
                subscription=sub,
            )

        # Recibo al cliente en cada cobro exitoso.
        card_info = None
        if sub and sub.card_last_four:
            card_info = f"{sub.card_brand} ****{sub.card_last_four}"
        owner_email = getattr(tenant.owner, "email", "")
        if owner_email:
            email_service.notify_client_payment_success(
                owner_email,
                amount=mp_payment.get("transaction_amount"),
                card_info=card_info,
            )

        return Response(status=status.HTTP_200_OK)

    # status_detail de MP que indican tarjeta vencida
    CARD_EXPIRED_DETAILS = {
        "cc_rejected_bad_filled_date",
        "cc_rejected_card_expired",
    }

    def _handle_rejected_payment(self, mp_payment, tenant):
        """Avisa al cliente de un pago rechazado (tarjeta vencida vs otro error)."""
        status_detail = mp_payment.get("status_detail", "")
        card = mp_payment.get("card") or {}
        last_four = card.get("last_four_digits") or ""
        pm = mp_payment.get("payment_method") or {}
        brand = pm.get("id") or mp_payment.get("payment_method_id") or ""
        card_info = f"{brand} ****{last_four}" if last_four else None

        owner_email = getattr(tenant.owner, "email", "")
        is_expired = status_detail in self.CARD_EXPIRED_DETAILS

        logger.info(
            f"[MPWebhook] payment rejected tenant={tenant.short_name} detail={status_detail} expired={is_expired}"
        )

        # Correo al cliente
        if owner_email:
            if is_expired:
                email_service.notify_client_card_expired(owner_email, card_info=card_info)
            else:
                email_service.notify_client_payment_failed(owner_email, card_info=card_info)

        # Notificación interna a soporte
        email_service.send_support_notification(
            subject=f"[{tenant.short_name}] Pago rechazado",
            context={
                "title": "Pago rechazado",
                "subtitle": "El cobro de la suscripción no se pudo procesar.",
                "status_label": "Tarjeta vencida" if is_expired else "Pago rechazado",
                "status_color": "#dc2626",
                "rows": [
                    {"label": "Negocio", "value": tenant.name},
                    {"label": "Short name", "value": tenant.short_name},
                    {"label": "Motivo (MP)", "value": status_detail},
                    {"label": "Tarjeta", "value": card_info},
                    {"label": "MP payment id", "value": mp_payment.get("id")},
                ],
            },
        )

    def _store_card_data(self, mp_payment):
        """
        Guarda marca, últimos 4 y vencimiento de la tarjeta en la Subscription
        correspondiente (localizada por el subscription_id del preapproval).
        Datos NO sensibles. Silencioso si no hay datos o no se localiza la sub.
        """
        try:
            poi = mp_payment.get("point_of_interaction") or {}
            tx = poi.get("transaction_data") or {}
            subscription_id = tx.get("subscription_id")
            if not subscription_id:
                return

            sub = Subscription.objects.filter(
                mp_subscription_id=str(subscription_id)
            ).first()
            if not sub:
                return

            card = mp_payment.get("card") or {}
            last_four = card.get("last_four_digits") or ""
            exp_month = card.get("expiration_month")
            exp_year = card.get("expiration_year")
            pm = mp_payment.get("payment_method") or {}
            brand = pm.get("id") or mp_payment.get("payment_method_id") or ""

            sub.card_brand = brand
            sub.card_last_four = last_four
            sub.card_expiration_month = exp_month
            sub.card_expiration_year = exp_year
            sub.save(update_fields=[
                "card_brand", "card_last_four",
                "card_expiration_month", "card_expiration_year",
            ])
            logger.info(f"[MPWebhook] card data stored for sub {subscription_id}: {brand} ****{last_four}")
        except Exception as e:
            logger.warning(f"[MPWebhook] could not store card data: {e}")

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

        # Vocabulario alineado con MP: se persiste el status directo, validando
        # contra los choices. Un estado desconocido se ignora (no corromper datos).
        valid_statuses = {choice[0] for choice in Subscription.STATUS_CHOICES}
        if new_status not in valid_statuses:
            logger.warning(f"[MPWebhook] unknown subscription status from MP: {new_status} (id={sub_id}), ignoring")
            return Response(status=status.HTTP_200_OK)

        try:
            subscription = Subscription.objects.get(mp_subscription_id=str(sub_id))
            subscription.status = new_status
            subscription.save(update_fields=["status"])
            logger.info(f"[MPWebhook] subscription {sub_id} updated to {subscription.status}")

            # NOTA: no marcamos Tenant.cancelled_at aquí. MP reporta 'cancelled'
            # tanto para cancelaciones voluntarias como para fallos de cobro /
            # tarjeta vencida, y no debemos tratar una tarjeta vencida como
            # "el cliente canceló". La cancelación de negocio (cancelled_at) la
            # marca ÚNICAMENTE el owner vía SubscriptionCancelView. Un preapproval
            # cancelado por fallo de cobro se refleja solo en Subscription.status;
            # el cliente pierde acceso por vigencia y el frontend le muestra
            # "actualiza tu tarjeta".
        except Subscription.DoesNotExist:
            logger.warning(f"[MPWebhook] subscription not found: mp_subscription_id={sub_id}")

        return Response(status=status.HTTP_200_OK)
