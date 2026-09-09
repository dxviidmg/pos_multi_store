from django.conf import settings

from .smtp_backend import SMTPBackend


class EmailService:
    """Fachada pública para envío de correos."""

    def __init__(self):
        provider = getattr(settings, 'EMAIL_BACKEND_PROVIDER', 'smtp')

        if provider == 'smtp':
            self.backend = SMTPBackend()
        else:
            raise ValueError(f'Proveedor de email no soportado: {provider}')

    def send_welcome_email(self, user_email: str, username: str, password: str):
        """Envía correo de bienvenida con credenciales de acceso."""
        from django.conf import settings
        context = {
            'username': username,
            'password': password,
            'frontend_url': getattr(settings, 'FRONTEND_URL', ''),
        }
        return self.backend.send(
            to=user_email,
            subject='¡Bienvenido a SmartVenta!',
            template_name='welcome',
            context=context,
        )


    def send_support_notification(self, subject: str, context: dict):
        """Envía una notificación interna al correo de soporte (plantilla genérica)."""
        from django.conf import settings
        support_email = getattr(settings, 'SUPPORT_EMAIL', '')
        if not support_email:
            return False
        return self.backend.send(
            to=support_email,
            subject=subject,
            template_name='support_notification',
            context=context,
        )

    def notify_new_tenant(self, tenant, subscription=None, plan=None):
        """Soporte: se registró un nuevo negocio (tenant + suscripción)."""
        rows = [
            {"label": "Negocio", "value": tenant.name},
            {"label": "Short name", "value": tenant.short_name},
            {"label": "Registrado", "value": tenant.created_at.strftime("%Y-%m-%d %H:%M")},
        ]
        if plan:
            rows.append({"label": "Plan", "value": f"{plan.name} · ${plan.price} · {plan.stores} tienda(s)"})
        rows.append({"label": "Propietario (email)", "value": getattr(tenant.owner, 'email', '')})
        rows.append({"label": "Usuario", "value": getattr(tenant.owner, 'username', '')})
        if subscription:
            rows.append({"label": "MP subscription id", "value": subscription.mp_subscription_id})
            rows.append({"label": "Email pagador", "value": subscription.payer_email})
        context = {
            "title": "Nuevo negocio registrado",
            "subtitle": "Se creó el tenant y su suscripción. Falta confirmar el primer pago.",
            "status_label": "Pago pendiente de confirmar",
            "status_color": "#b45309",
            "rows": rows,
        }
        return self.send_support_notification(
            subject=f"[{tenant.short_name}] Nuevo negocio registrado",
            context=context,
        )

    def notify_first_payment(self, tenant, amount=None, payment_id=None, subscription=None):
        """Soporte: se registró el primer pago de un negocio."""
        rows = [
            {"label": "Negocio", "value": tenant.name},
            {"label": "Short name", "value": tenant.short_name},
            {"label": "Monto", "value": f"${amount}" if amount is not None else None},
            {"label": "MP payment id", "value": payment_id},
        ]
        if subscription:
            rows.append({"label": "MP subscription id", "value": subscription.mp_subscription_id})
            if subscription.card_last_four:
                rows.append({"label": "Tarjeta", "value": f"{subscription.card_brand} ****{subscription.card_last_four}"})
        context = {
            "title": "Primer pago recibido",
            "subtitle": "El negocio quedó al corriente.",
            "status_label": "Pago confirmado",
            "status_color": "#047857",
            "rows": rows,
        }
        return self.send_support_notification(
            subject=f"[{tenant.short_name}] Primer pago recibido",
            context=context,
        )


    def _client_payment_email(self, user_email, subject, context):
        from django.conf import settings
        context.setdefault('frontend_url', getattr(settings, 'FRONTEND_URL', ''))
        return self.backend.send(
            to=user_email,
            subject=subject,
            template_name='payment_notification',
            context=context,
        )

    def notify_client_payment_success(self, user_email, amount=None, card_info=None):
        """Cliente: cobro exitoso (recibo)."""
        return self._client_payment_email(
            user_email,
            subject="Pago recibido · SmartVenta",
            context={
                "title": "¡Pago recibido!",
                "message": "Confirmamos el cobro de tu suscripción a SmartVenta. Gracias por seguir con nosotros.",
                "status_color": "#047857",
                "amount": amount,
                "card_info": card_info,
                "cta_label": "Ir a SmartVenta",
            },
        )

    def notify_client_payment_failed(self, user_email, card_info=None):
        """Cliente: hubo un error en el pago."""
        return self._client_payment_email(
            user_email,
            subject="Problema con tu pago · SmartVenta",
            context={
                "title": "Hubo un problema con tu pago",
                "message": "No pudimos procesar el cobro de tu suscripción. Por favor revisa tu método de pago o actualiza tu tarjeta para no perder el servicio.",
                "status_color": "#b45309",
                "card_info": card_info,
                "cta_label": "Actualizar tarjeta",
            },
        )

    def notify_client_card_expired(self, user_email, card_info=None):
        """Cliente: su tarjeta venció."""
        return self._client_payment_email(
            user_email,
            subject="Tu tarjeta venció · SmartVenta",
            context={
                "title": "Tu tarjeta venció",
                "message": "El cobro de tu suscripción no se pudo realizar porque tu tarjeta venció. Actualízala para seguir usando SmartVenta sin interrupciones.",
                "status_color": "#dc2626",
                "card_info": card_info,
                "cta_label": "Actualizar tarjeta",
            },
        )


    def notify_tenant_without_payment(self, tenant, hours=24):
        """Soporte: alerta de tenant registrado sin pago tras X horas."""
        rows = [
            {"label": "Negocio", "value": tenant.name},
            {"label": "Short name", "value": tenant.short_name},
            {"label": "Registrado", "value": tenant.created_at.strftime("%Y-%m-%d %H:%M")},
            {"label": "Propietario (email)", "value": getattr(tenant.owner, 'email', '')},
        ]
        sub = tenant.subscription_set.order_by("-created_at").first()
        if sub:
            rows.append({"label": "MP subscription id", "value": sub.mp_subscription_id})
            rows.append({"label": "Estado MP", "value": sub.get_status_display()})
        return self.send_support_notification(
            subject=f"[{tenant.short_name}] 🚨 Sin pago tras {hours}h",
            context={
                "title": "Tenant registrado sin pago",
                "subtitle": f"Se registró hace más de {hours}h y aún no tiene ningún pago.",
                "status_label": "Requiere seguimiento",
                "status_color": "#dc2626",
                "rows": rows,
                "note": "Revisa si el pago falló o el webhook de MP no llegó.",
            },
        )


email_service = EmailService()
