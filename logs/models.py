from django.db import models
from django.contrib.auth.models import User
from tenants.models import CreatedAtModel
from products.models import StoreProduct, Store


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
    store_related = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="store_related", null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    previous_stock = models.IntegerField()
    updated_stock = models.IntegerField()
    action = models.CharField(max_length=1, choices=ACTIONS_CHOICES)
    movement = models.CharField(max_length=2, choices=MOVEMENT_CHOICES, default="MA")

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
        if self.store_related:
            if self.action == "S":
                return "{} {} Destino: {}".format(self.get_action_display(), self.get_movement_display(), self.store_related.get_full_name())            
            return "{} {} Origen: {}".format(self.get_action_display(), self.get_movement_display(), self.store_related.get_full_name())            
        return "{} {}".format(self.get_action_display(), self.get_movement_display())

    def calculate_difference(self):
        difference = self.updated_stock - self.previous_stock
        return f"+{difference}" if difference > 0 else str(difference)
    
    
    def is_repeated(self):
        previous_obj = (
            StoreProductLog.objects
            .filter(
                store_product=self.store_product,
                action=self.action,
                movement=self.movement,
                pk__lt=self.pk,
            )
            .order_by("-pk")
            .only("created_at")  # 🔹 optimiza la consulta
            .first()
        )

        return bool(previous_obj and (self.created_at - previous_obj.created_at).total_seconds() < 1)
    
    def is_consistent(self):
        previous_obj = (
            StoreProductLog.objects
            .filter(store_product=self.store_product, pk__lt=self.pk)
            .order_by("-pk")
            .only("updated_stock")  # 🔹 solo trae el campo necesario
            .first()
        )
        return not previous_obj or self.previous_stock == previous_obj.updated_stock
    
    def has_negatives(self):
        return self.previous_stock < 0 or self.updated_stock < 0