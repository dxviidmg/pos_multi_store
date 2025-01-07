from django.db import models
from products.models import Base
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator
from tenants.models import Tenant
from django.db.models import Q


class Discount(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    discount_percentage = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    def __str__(self):
        return "{}%".format(self.discount_percentage)

    def get_discount_percentage_complement(self):
        return 100 - self.discount_percentage

    class Meta:
        unique_together = ('tenant', 'discount_percentage')

class Client(models.Model):
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=10, validators=[MinLengthValidator(10)])

    def get_full_name(self):
        return "{} {}".format(self.first_name, self.last_name)

    def __str__(self):
        return self.get_full_name()

#    class Meta:
#        constraints = [
#            models.UniqueConstraint(
#                fields=['phone_number'],
#                condition=Q(discount__tenant=models.F('discount__tenant')),
#                name='unique_tenant_phone_number'
#            )
#        ]