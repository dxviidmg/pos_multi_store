import logging

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

from .base import EmailBackend

logger = logging.getLogger(__name__)


class SMTPBackend(EmailBackend):
    """Backend de envío de correo vía SMTP (Gmail, etc.)."""

    def send(self, to: str, subject: str, template_name: str, context: dict) -> bool:
        try:
            html_content = render_to_string(f'email/{template_name}.html', context)

            msg = EmailMultiAlternatives(
                subject=subject,
                body='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to],
            )
            msg.attach_alternative(html_content, 'text/html')
            msg.send()

            logger.info(f'Correo enviado a {to}: {subject}')
            return True

        except Exception as e:
            logger.error(f'Error enviando correo a {to}: {e}')
            return False
