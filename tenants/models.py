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
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=5, unique=True)
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    is_sandbox = models.BooleanField(default=False)
    displays_stock_in_storages = models.BooleanField(default=False)
    create_products_on_sale = models.BooleanField(default=True)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, null=True, blank=True)

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
        sub = self.subscription_set.filter(status="authorized").first()
        if sub and sub.plan:
            return sub.plan
        return self.plan

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
        ("active", "Activa"),
        ("paused", "Pausada"),
        ("cancelled", "Cancelada"),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    mp_subscription_id = models.CharField(max_length=100, unique=True)
    card_token_id = models.CharField(max_length=255, default='')
    payment_method_id = models.CharField(max_length=50, default="credit_card")  # credit_card o debit_card
    payer_email = models.EmailField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

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
