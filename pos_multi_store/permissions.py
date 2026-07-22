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
        return api_key == settings.PUBLIC_API_KEY
