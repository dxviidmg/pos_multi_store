from abc import ABC, abstractmethod


class EmailBackend(ABC):
    """Clase abstracta para backends de envío de correo."""

    @abstractmethod
    def send(self, to: str, subject: str, template_name: str, context: dict) -> bool:
        """
        Envía un correo electrónico.

        Args:
            to: Dirección de correo del destinatario.
            subject: Asunto del correo.
            template_name: Nombre de la plantilla HTML (sin extensión).
            context: Diccionario con variables para renderizar la plantilla.

        Returns:
            True si se envió correctamente, False en caso de error.
        """
        pass
