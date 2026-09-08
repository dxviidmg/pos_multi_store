from django.conf import settings
from rest_framework.permissions import BasePermission


class HasAPIKey(BasePermission):
    """
    Permite acceso si el request incluye un header X-API-Key válido.
    Útil para endpoints públicos que no requieren login pero necesitan
    un mínimo de seguridad para evitar acceso no autorizado.
    """

    def has_permission(self, request, view):
        api_key = request.headers.get("X-API-Key", "")
        print(api_key)
        return api_key == settings.PUBLIC_API_KEY


class TenantHasAccess(BasePermission):
    """
    Bloquea el acceso a la API de negocio cuando el tenant venció
    (pasó el fin del periodo pagado). Se evalúa en CADA request porque los
    tokens ya emitidos no caducan solos.

    Reglas:
      - Tenant vigente -> acceso permitido.
      - Tenant vencido + owner -> acceso SOLO a la payment_allowlist (modo pago).
      - Tenant vencido + no owner -> bloqueado en todo.

    Los endpoints públicos (login, webhook MP, alta pública, planes) NO deben
    usar este permission class; se mantienen fuera del gate.
    """

    message = {
        "detail": "Tu suscripción venció. Renueva para continuar.",
        "code": "subscription_expired",
    }

    # Endpoints (url_name del namespace 'tenants') que un owner vencido SÍ puede
    # usar para pagar/renovar. Todo lo demás queda bloqueado.
    PAYMENT_ALLOWLIST = {
        "current-plan",
        "plan-equivalent",
        "subscriptions-create",
        "subscription-detail",
        "mercadopago-preference",
        "tenant-info",
        "tenant-dates",
    }

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            # La autenticación la maneja IsAuthenticated; aquí no bloqueamos.
            return True

        tenant = user.get_tenant()
        if tenant is None:
            return True

        if tenant.has_access():
            return True

        # Tenant vencido: solo el owner puede acceder a la allowlist de pago.
        if user.get_role() == "owner":
            match = getattr(request, "resolver_match", None)
            url_name = match.url_name if match else None
            return url_name in self.PAYMENT_ALLOWLIST

        return False
