from django.db import models
from clients.models import Client
from products.models import Product, Store
from django.contrib.auth.models import User


class Sale(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sales')
    #Despues de prod quitar el null y blank
    saler = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return "{} {}".format(self.id, self.created_at)
    
    def is_cancelable(self):
        payments = self.payments.all()
        return payments.count() == 1 and payments.filter(payment_method='EF').exists()

    def get_payments_methods_display(self):
        return [payment.get_payment_method_display() for payment in self.payments.all()]


class ProductSale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_sales')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='products_sale')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def get_total(self):
        return self.quantity * self.price



class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ("EF", "Efectivo"),
        ("TA", "Tarjeta"),
        ("TR", "Transferencia"),
    )
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    payment_method = models.CharField(max_length=2, choices=PAYMENT_METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
