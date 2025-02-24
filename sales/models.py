from django.db import models
from clients.models import Client
from products.models import Product, Store
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator
import socket

class Sale(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="sales")
    saler = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return "{} {}".format(self.id, self.created_at)

    def is_cancelable(self):
        payments = self.payments.all()
        return payments.count() == 1 and payments.filter(payment_method="EF").exists()

    def get_payments_methods_display(self):
        return [payment.get_payment_method_display() for payment in self.payments.all()]

    def get_profit(self):
        profit = 0
        for product_sale in self.products_sale.all():
            profit = profit + product_sale.get_profit()

        return profit


class ProductSale(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_sales"
    )
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name="products_sale"
    )
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def get_total(self):
        return self.quantity * self.price

    def get_profit(self):
        return (self.price - self.product.cost) * self.quantity


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ("EF", "Efectivo"),
        ("TA", "Tarjeta"),
        ("TR", "Transferencia"),
    )
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    payment_method = models.CharField(max_length=2, choices=PAYMENT_METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)



class Printer(models.Model):

    CONNECTION_TYPE_CHOICES = [("USB", "USB"), ("WIFI", "WIFI")]

    store = models.OneToOneField(Store, on_delete=models.CASCADE)
    connection_type = models.CharField(max_length=4, choices=CONNECTION_TYPE_CHOICES)
    ip = models.GenericIPAddressField(protocol="ipv4")  # Solo para direcciones IPv4
    port = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )  # Validación para el puerto

    # USB
    def send_print_via_intermediary(self, content):
        print(socket.AF_INET, socket.SOCK_STREAM)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as printer_socket:
            print(self.ip, self.port)
            printer_socket.connect((self.ip, self.port))
            print('printer_socket', printer_socket)
            printer_socket.sendall(content.encode("utf-8"))
            response = printer_socket.recv(1024)
        print('response', response)
        return response.decode("utf-8")

    # WIFI
    def send_print_via_wifi(self, content):
        printer = Network(self.ip, self.port)

        # Enviar datos a la impresora
        printer.text(content)
        printer.cut()  # Descomentar si se requiere cortar después de imprimir
        return "Ticket enviado a la impresora exitosamente"

    def send_print(self, content):
        """
        Método polimórfico para enviar impresión según el tipo de conexión.
        """
        if self.connection_type == "USB":
            return self.send_print_via_intermediary(content)
        elif self.connection_type == "WIFI":
            return self.send_print_via_wifi(content)
        else:
            raise ValueError("Tipo de conexión inválido")

    def get_url(self):
        return "http://" + self.ip + ':' + str(self.port)