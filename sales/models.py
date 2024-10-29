from django.db import models
from django.contrib.auth.models import User
from clients.models import Client
from products.models import Product

class Sale(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    saler = models.ForeignKey(User, on_delete=models.CASCADE)


class SaleProduct(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (('E', 'Efectivo'), ('P', 'Pago con tarjeta'), ('T', 'Transferencia'))
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)
    payment_method = models.CharField(max_length=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    