from django.contrib.auth.models import User
from django.db import models

from core.constants import LogAction, LogMovement
from products.models import Store, StoreProduct, Product
from tenants.models import CreatedAtModel


class StoreProductLog(CreatedAtModel):
    store_product = models.ForeignKey(
        StoreProduct, on_delete=models.CASCADE, related_name="store_product_logs"
    )
    store_related = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="store_related", null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    previous_stock = models.IntegerField()
    updated_stock = models.IntegerField()
    action = models.CharField(max_length=1, choices=LogAction.choices)
    movement = models.CharField(max_length=2, choices=LogMovement.choices, default=LogMovement.MANUAL)

    class Meta:
        indexes = [
            models.Index(fields=['store_product', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'movement', 'created_at']),
        ]

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


class ProductPriceLog(CreatedAtModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="price_logs"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    field = models.CharField(max_length=50)  # cost, unit_price, wholesale_price
    previous_value = models.CharField(max_length=50, null=True)
    new_value = models.CharField(max_length=50, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['product', 'created_at']),
        ]

    def __str__(self):
        return f"{self.product} {self.field}: {self.previous_value} -> {self.new_value}"