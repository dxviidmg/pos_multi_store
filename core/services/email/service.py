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
        context = {
            'username': username,
            'password': password,
        }
        return self.backend.send(
            to=user_email,
            subject='¡Bienvenido a SmartVenta!',
            template_name='welcome',
            context=context,
        )


email_service = EmailService()
