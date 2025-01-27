from django.db import models
from django.contrib.auth.models import User
from tenants.models import Tenant, TimeStampedModel
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError


class Base(models.Model):
    name = models.CharField(max_length=30)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(Base):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    def get_product_count(self):
        return self.products.count()

class Store(Base):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    STORE_TYPE_CHOICES = (("A", "Almacen"), ("T", "Tienda"))
    store_type = models.CharField(max_length=1, choices=STORE_TYPE_CHOICES)
    manager = models.OneToOneField(User, on_delete=models.CASCADE)

    def get_full_name(self):
        return "{} {}".format(self.get_store_type_display(), self.name)

    def __str__(self):
        return self.get_full_name()
    
    def save(self, *args, **kwargs):
        if not self.pk:  # Solo para nuevos objetos
            username = (f"{self.tenant.short_name}.{self.get_store_type_display().lower()}.{self.name.replace(' ', '_').lower()}")
            first_name = username.replace(".", " ").title()

            # Crear o recuperar al usuario propietario
            self.manager, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "password": make_password(username),
                },
            )

        super().save(*args, **kwargs)


class Product(Base):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    wholesale_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    min_wholesale_quantity = models.IntegerField(null=True, blank=True)
    wholesale_price_on_client_discount = models.BooleanField(default=False)

    def clean(self):
        if (
            Product.objects.filter(code=self.code, brand__tenant=self.brand.tenant)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError({"code": "product with this code already exists."})

    def get_description(self):
        return "{} {}".format(self.brand.name, self.name).strip()

    def get_description(self):
        return "{} {}".format(self.brand.name, self.name).strip()

    def apply_wholesale(self):
        return (
            self.wholesale_price is not None
            and self.min_wholesale_quantity is not None
        )


class StoreProduct(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    stock = models.IntegerField(default=0)

    def __str__(self):
        return self.product.__str__() + " " + self.store.__str__()

    def calculate_reserved_stock(self):
        transfers = self.store.transfers_from.filter(
            product=self.product, transfer_datetime=None
        )

        return sum(transfer.quantity for transfer in transfers)

    def calculate_available_stock(self):
        return self.stock - self.calculate_reserved_stock()


class Transfer(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    origin_store = models.ForeignKey(
        Store, related_name="transfers_from", on_delete=models.CASCADE
    )
    destination_store = models.ForeignKey(
        Store, related_name="transfers_to", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    transfer_datetime = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Transfer of {self.quantity} {self.product.name} from {self.origin_store.name} to {self.destination_store.name}"


class StoreProductLog(TimeStampedModel):
    ACTIONS_CHOICES = [
        ('E', 'Entrada'),
        ('S', 'Salida'),
        ('A', 'Ajuste')
    ]

    MOVEMENT_CHOICES = [
        ('DI', 'Distribución'),
        ('TR', 'Transferencia'),
        ('DE', 'Devolucíon'), #Cancelación de compra
        ('VE', 'Venta'),
        ('MA', 'Manual')
    ]
        
    store_product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name='store_product_logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    previous_stock = models.IntegerField()
    updated_stock = models.IntegerField()
    action = models.CharField(max_length=1, choices=ACTIONS_CHOICES)
    movement = models.CharField(max_length=2, choices=MOVEMENT_CHOICES, default='MA')


    def __str__(self):
        return "{} {} {} {} {}".format(self.store_product, self.action, self.movement, self.previous_stock, self.updated_stock)
    

    def get_description(self):
        return "{} {}".format(self.get_action_display(), self.get_movement_display())
    
    def calculate_difference(self):
        difference = self.updated_stock - self.previous_stock
        return f"+{difference}" if difference > 0 else str(difference)