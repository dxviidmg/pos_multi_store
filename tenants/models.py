from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from dateutil.relativedelta import relativedelta

MONTHY_PRICE_BY_STORE = 500


class CreatedAtModel(models.Model):
    """Abstract base class that adds created_at and updated_at fields to models."""

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Plan(models.Model):
    BILLING_TYPE_CHOICES = [
        ("S", "Suscripción"),
        ("M", "Manual"),
    ]
    name = models.CharField(max_length=30)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    stores = models.IntegerField()
    billing_type = models.CharField(max_length=1, choices=BILLING_TYPE_CHOICES)
    # Mercado Pago (vacío si el plan no está en MP)
    mp_plan_id = models.CharField(max_length=100, blank=True, null=True)
    is_sandbox = models.BooleanField(default=False) 
    
    def __str__(self):
        return self.name
    

class Tenant(CreatedAtModel):
    CANCELLATION_REASON_CHOICES = [
        ("price", "Precio"),
        ("not_using", "No lo uso"),
        ("switched_tool", "Cambié de herramienta"),
        ("missing_features", "Faltan funciones"),
        ("technical_issues", "Problemas técnicos"),
        ("business_closed", "Cerró el negocio"),
        ("other", "Otro"),
    ]

    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=10, unique=True)
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    is_sandbox = models.BooleanField(default=False)
    displays_stock_in_storages = models.BooleanField(default=False)
    create_products_on_sale = models.BooleanField(default=True)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, null=True, blank=True)
    # Cancelación a nivel negocio (no es el status de MP, que vive en Subscription).
    # Estado cancelado = (cancelled_at IS NOT NULL).
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(
        max_length=30, choices=CANCELLATION_REASON_CHOICES, blank=True, default=""
    )
    # Marca para no reenviar la alerta interna de "sin pago tras 24h".
    no_payment_alert_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.pk:  # Solo para nuevos objetos
            # Crear un username y nombre para el propietario
            username = f"{self.short_name}.propietario"
            first_name = username.replace(".", " ").title()

            # Crear o recuperar al usuario propietario
            self.owner, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "password": make_password(username),
                },
            )

        super().save(*args, **kwargs)

    def get_plan(self):
        # Subscription ya no tiene campo 'plan' (eliminado en migración 0013).
        # El plan del tenant vive en self.plan; el filtro por suscripción se
        # mantiene solo por claridad histórica, pero la fuente es self.plan.
        return self.plan

    @property
    def is_cancelled(self):
        """Estado de negocio derivado: cancelado si cancelled_at tiene valor."""
        return self.cancelled_at is not None

    def subscription_status(self):
        """
        Estado de negocio derivado con 3 valores:
          - 'cancelled': el owner canceló voluntariamente (cancelled_at marcado).
          - 'expired': MP dejó la última suscripción en paused/cancelled por
                       fallo de cobro/tarjeta y el owner NO canceló.
          - 'active': en cualquier otro caso.
        NOTA: 'expired' NO corta el acceso; el acceso depende de la vigencia.
        """
        if self.cancelled_at is not None:
            return "cancelled"
        last_sub = self.subscription_set.order_by("-created_at").first()
        if last_sub and last_sub.status in ("paused", "cancelled"):
            return "expired"
        return "active"

    def current_card(self):
        """Datos de tarjeta de la última suscripción, o None."""
        last_sub = self.subscription_set.order_by("-created_at").first()
        if not last_sub or not last_sub.card_last_four:
            return None
        exp = None
        if last_sub.card_expiration_month and last_sub.card_expiration_year:
            exp = f"{last_sub.card_expiration_month:02d}/{str(last_sub.card_expiration_year)[-2:]}"
        return {
            "brand": last_sub.card_brand,
            "last_four": last_sub.card_last_four,
            "expiration": exp,
        }

    def access_until(self):
        """Fecha (date) hasta la que el tenant conserva acceso: fin del último periodo pagado."""
        last_payment = (
            Payment.objects.filter(tenant=self).order_by("-end_of_validity").first()
        )
        return last_payment.end_of_validity if last_payment else None

    def has_access(self):
        """
        True si hoy <= end_of_validity (inclusive), en hora local (America/Mexico_City).

        PROVISIONAL: si el tenant aún no tiene ningún Payment se concede acceso
        (return True), porque hoy el primer Payment se crea vía webhook de MP y
        puede tardar/fallar. TODO: endurecer a False cuando el Payment se cree
        en el alta (PublicTenantCreateView).
        """
        until = self.access_until()
        if until is None:
            return True
        return timezone.localdate() <= until

    def count_products(self):
        from products.models import Product
        return Product.objects.filter(brand__tenant=self).count()
    

class Payment(CreatedAtModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    months = models.IntegerField(default=1)
    total = models.DecimalField(decimal_places=2, max_digits=7, default=0)
    start_of_validity = models.DateField(default=timezone.now)
    end_of_validity = models.DateField(default=timezone.now)
    mp_external_reference = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.pk:  # Solo para nuevos objetos
            tenant = self.tenant
            plan = tenant.get_plan()
            self.total = plan.price * self.months if plan else 0

            last_payment = Payment.objects.filter(
                tenant=tenant
            ).last()  # .end_of_validity

            if last_payment:
                start_of_validity = last_payment.end_of_validity + relativedelta(days=1)
            else:
                start_of_validity = tenant.created_at

            end_of_validity = (
                start_of_validity + relativedelta(months=self.months) - relativedelta(days=1)
            )
            self.start_of_validity = start_of_validity
            self.end_of_validity = end_of_validity

        super().save(*args, **kwargs)


class Subscription(CreatedAtModel):
    """Suscripción activa de un tenant."""
    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("authorized", "Autorizada"),
        ("paused", "Pausada"),
        ("cancelled", "Cancelada"),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    mp_subscription_id = models.CharField(max_length=100, unique=True)
    card_token_id = models.CharField(max_length=255, default='')
    payment_method_id = models.CharField(max_length=50, default="credit_card")  # credit_card o debit_card
    payer_email = models.EmailField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="authorized")
    # Datos NO sensibles de la tarjeta (para que el cliente identifique cuál usó).
    # Se capturan desde el webhook del pago (card.* y payment_method.id de MP).
    card_brand = models.CharField(max_length=20, blank=True, default="")
    card_last_four = models.CharField(max_length=4, blank=True, default="")
    card_expiration_month = models.IntegerField(null=True, blank=True)
    card_expiration_year = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.tenant} - {self.status}"


class SubscriptionPayment(CreatedAtModel):
    """Pago recurrente procesado por MP."""
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    mp_payment_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.subscription.tenant} - ${self.amount} - {self.status}"
