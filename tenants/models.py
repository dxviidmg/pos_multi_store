from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from dateutil.relativedelta import relativedelta

MONTHY_PRICE_BY_STORE = 500

class TimeStampedModel(models.Model):
    """Abstract base class that adds created_at and updated_at fields to models."""

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Tenant(TimeStampedModel):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=5, unique=True)
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    stores = models.IntegerField()
    is_sandbox = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.pk:  # Solo para nuevos objetos
            # Crear un username y nombre para el propietario
            username = f"{self.short_name}.owner"
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

class Payment(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    months = models.IntegerField(default=1)
    total = models.DecimalField(decimal_places=2, max_digits=7, default=0)
    start_of_validity = models.DateField(default=timezone.now)
    end_of_validity = models.DateField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.pk:  # Solo para nuevos objetos
            tenant = self.tenant
            self.total = tenant.stores * self.months * MONTHY_PRICE_BY_STORE

            last_payment = Payment.objects.filter(
                tenant=tenant
            ).last()  # .end_of_validity

            if last_payment:
                start_of_validity = last_payment.end_of_validity + relativedelta(days=1)
            else:
                start_of_validity = tenant.created_at

            end_of_validity = (
                start_of_validity + relativedelta(months=1) - relativedelta(days=1)
            )
            self.start_of_validity = start_of_validity
            self.end_of_validity = end_of_validity

        super().save(*args, **kwargs)
