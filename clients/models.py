from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator
from tenants.models import Tenant
from django.db.models import Sum


class Discount(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    discount_percentage = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    def __str__(self):
        return "{}% {}".format(self.discount_percentage, self.tenant)

    def get_discount_percentage_complement(self):
        return 100 - self.discount_percentage

    class Meta:
        unique_together = ['tenant', 'discount_percentage']

class Client(models.Model):
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=10, validators=[MinLengthValidator(10)])

    def get_full_name(self):
        return "{} {}".format(self.first_name, self.last_name)

    def __str__(self):
        return self.get_full_name()
    

    def get_total_sales_amount(self, start_date, end_date):
        total = self.sales.filter(
            created_at__date__range=(start_date, end_date)
        ).aggregate(total_amount=Sum("total"))["total_amount"]
        return total or 0
