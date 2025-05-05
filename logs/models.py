from django.db import models
from django.contrib.auth.models import User
from tenants.models import CreatedAtModel
from products.models import StoreProduct
from sales.models import Sale

class StoreProductLog(CreatedAtModel):
    ACTIONS_CHOICES = [("E", "Entrada"), ("S", "Salida"), ("A", "Ajuste"), ("N", "NA")]

    MOVEMENT_CHOICES = [
        ("MA", "Manual"),
        ("IM", "Importación"),
        ("DI", "Distribución"),
        ("TR", "Transferencia"),
        ("DE", "Devolucíon"),
        ("VE", "Venta"),
        ("AP", "Apartado"),
    ]

    store_product = models.ForeignKey(
        StoreProduct, on_delete=models.CASCADE, related_name="store_product_logs"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    previous_stock = models.IntegerField()
    updated_stock = models.IntegerField()
    action = models.CharField(max_length=1, choices=ACTIONS_CHOICES)
    movement = models.CharField(max_length=2, choices=MOVEMENT_CHOICES, default="MA")
#    sale = models.ForeignKey(Sale, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return "{} {} {} {} {}".format(
            self.store_product,
            self.action,
            self.movement,
            self.previous_stock,
            self.updated_stock,
        )

    def get_description(self):
        if self.get_action_display() == 'NA':
            return self.get_movement_display()
        return "{} {}".format(self.get_action_display(), self.get_movement_display())

    def calculate_difference(self):
        difference = self.updated_stock - self.previous_stock
        return f"+{difference}" if difference > 0 else str(difference)