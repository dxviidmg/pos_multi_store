from django.db import models
from clients.models import Client
from products.models import Product, Store
from django.contrib.auth.models import User
from tenants.models import CreatedAtModel
from django.db.models import Sum


class Sale(CreatedAtModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, related_name='sales')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="sales")
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    reservation_in_progress = models.BooleanField(default=False)
    is_canceled = models.BooleanField(default=False)

    
    def __str__(self):
        return "{} {}".format(self.id, self.created_at)

    def has_only_cash_payment(self):
        payments = self.payments.all()
        return payments.count() == 1 and payments.filter(payment_method="EF").exists()

    def get_refunded(self):
        refunded = 0
        for product_sale in self.products_sale.exclude(returned_quantity=0):
            refunded = refunded + product_sale.get_refunded()

        return refunded
        
    def is_cancelable(self):
        return (
            not self.reservation_in_progress and
            self.has_only_cash_payment() and
            self.get_refunded() == 0
        )

    def get_payments_methods_display(self):
        return [payment.get_payment_method_display() for payment in self.payments.all()]
    
    def get_reference(self):
        return next((payment.reference for payment in self.payments.all() if payment.reference), None)

    def get_profit(self):
        profit = 0
        for product_sale in self.products_sale.all():
            profit = profit + product_sale.get_profit()

        return profit
    
    def get_paid(self):
        return self.payments.all().aggregate(total_amount=Sum('amount'))['total_amount'] or 0
        

        

class ProductSale(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_sales"
    )
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name="products_sale"
    )
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    returned_quantity = models.IntegerField(default=0)

    def get_total(self):
        return self.quantity * self.price

    def get_profit(self):
        return (self.price - self.product.cost) * self.quantity

    def get_refunded(self):
        return self.returned_quantity * self.price
    
class Payment(CreatedAtModel):
    PAYMENT_METHOD_CHOICES = (
        ("EF", "Efectivo"),
        ("TA", "Tarjeta"),
        ("TR", "Transferencia"),
    )
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    payment_method = models.CharField(max_length=2, choices=PAYMENT_METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True, null=True)