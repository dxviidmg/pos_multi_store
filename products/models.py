from django.db import models
from django.contrib.auth.models import User

# traspasos, un vendedor hace traspasos, se crea, el registro de tienda a tienda, que fue y cuanto


class Base(models.Model):
    name = models.CharField(max_length=30)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(Base):
    pass


class Store(Base):
    STORE_TYPE_CHOICES = (("A", "Almacen"), ("T", "Tienda"))
    store_type = models.CharField(max_length=1, choices=STORE_TYPE_CHOICES)
    manager = models.OneToOneField(User, on_delete=models.CASCADE)

    def get_full_name(self):
        return "{}: {}".format(self.get_store_type_display(), self.name)

    def __str__(self):
        return self.get_full_name()

    def save(self, *args, **kwargs):
        # Guardar el producto primero
        super().save(*args, **kwargs)

        # Crear una entrada de StoreProduct para cada tienda
        products = Product.objects.all()
        for product in products:
            StoreProduct.objects.get_or_create(store=self, product=product)


class Product(Base):
    name = models.CharField(max_length=100)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    code = models.CharField(max_length=20, unique=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    wholesale_sale_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    min_wholesale_quantity = models.PositiveIntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Guardar el producto primero
        super().save(*args, **kwargs)

        # Crear una entrada de StoreProduct para cada tienda
        stores = Store.objects.all()
        for store in stores:
            StoreProduct.objects.get_or_create(store=store, product=self)

    def get_description(self):
        return "{} {}".format(self.brand.name, self.name).strip()


class StoreProduct(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    stock = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.product.__str__() + " " + self.store.__str__()

    def calculate_available_stock(self):
        transfers = self.store.transfers_from.filter(
            product=self.product,
            transfer_datetime=None,  # Opcional: considerar solo transferencias no entregadas
        )

        return self.stock - sum(transfer.quantity for transfer in transfers)


class ProductTransfer(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    origin_store = models.ForeignKey(
        Store, related_name="transfers_from", on_delete=models.CASCADE
    )
    destination_store = models.ForeignKey(
        Store, related_name="transfers_to", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    transfer_datetime = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Transfer of {self.quantity} {self.product.name} from {self.origin_store.name} to {self.destination_store.name}"


def get_store(self):
    return Store.objects.filter(manager=self).first()


User.add_to_class("get_store", get_store)
