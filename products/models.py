from django.db import models
from django.contrib.auth.models import User
from tenants.models import Tenant, CreatedAtModel
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db.models import Q

class Base(models.Model):
    name = models.CharField(max_length=30)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(Base):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, db_index=True)

    def count_products(self):
        return self.products.count()

class Department(Base):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    def count_products(self):
        return self.products.count()
    
class Store(Base):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    STORE_TYPE_CHOICES = (("A", "Almacen"), ("T", "Tienda"))
    store_type = models.CharField(max_length=1, choices=STORE_TYPE_CHOICES)
    manager = models.OneToOneField(User, on_delete=models.CASCADE)
    address = models.CharField(max_length=30, null=True, blank=True)
    phone_number = models.CharField(max_length=10, null=True, blank=True)

    def get_full_name(self):
        return "{} ({})".format(self.name, self.get_store_type_display(), )

    def __str__(self):
        return self.get_full_name()

    def save(self, *args, **kwargs):
        if not self.pk:  # Solo para nuevos objetos
            username = f"{self.tenant.short_name}.{self.get_store_type_display().lower()}.{self.name.replace(' ', '_').lower()}"
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

    def get_store_printer(self):
        store_printer = self.printer.filter(store=self).first()

        if store_printer:
            return store_printer.id
        return False

    def get_investment(self):
        store_products = self.store_products.all()
        store_investment = 0
        for store_product in store_products:
            if store_product.stock == 0:
                continue

            store_investment_by_product = (
                store_product.stock * store_product.product.cost
            )

            store_investment += store_investment_by_product

        return store_investment

    def count_products(self):
        return self.store_products.all().count()

    def count_workers(self):
        return self.workers.all().count()

    def count_pending_distributions(self):
        return Distribution.objects.filter(
            Q(origin_store=self) | Q(destination_store=self), transfer_datetime=None
        ).count()
    
    def count_pending_transfers(self):
        return Transfer.objects.filter(
            Q(origin_store=self) | Q(destination_store=self), transfer_datetime=None, distribution=None
        ).count()

class Product(Base):
    def path(self, filename):
        return "{0}/products/{1}".format(
            self.brand.tenant.short_name,
            filename,
        )

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="products")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="products", null=True, blank=True)
    code = models.CharField(max_length=20, db_index=True)
    name = models.CharField(max_length=100)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    wholesale_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    min_wholesale_quantity = models.IntegerField(null=True, blank=True)
    wholesale_price_on_client_discount = models.BooleanField(default=False)
    image = models.ImageField(upload_to=path, null=True, blank=True)

    def clean(self):
        if (
            Product.objects.filter(code=self.code, brand__tenant=self.brand.tenant)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError({"code": "product with this code already exists."})

    def get_description(self):
        return "{} {}".format(self.brand.name, self.name).strip()

    def apply_wholesale(self):
        return (
            self.wholesale_price is not None and self.min_wholesale_quantity is not None
        )

    def get_stock(self):
        return (
            self.product_stores.aggregate(total_stock=Sum("stock"))["total_stock"] or 0
        )

    class Meta:
        indexes = [
            models.Index(fields=["code", "brand"]),
        ]

class StoreProduct(models.Model):
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="store_products"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_stores"
    )
    stock = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["store", "product"]),
        ]
        
    def __str__(self):
        return self.product.__str__() + " " + self.store.__str__()

    def calculate_reserved_stock(self):
        transfers = self.store.transfers_from.filter(
            product=self.product, transfer_datetime=None
        )
        stock_reserved_in_transfers = sum(transfer.quantity for transfer in transfers)
        stock_reserved_in_reservations = (
            self.store.sales
            .filter(reservation_in_progress=True, products_sale__product=self.product)
            .aggregate(total_quantity=Sum('products_sale__quantity'))['total_quantity'] or 0
        )

        return stock_reserved_in_transfers + stock_reserved_in_reservations

    def calculate_available_stock(self):
        return self.stock - self.calculate_reserved_stock()

class Distribution(CreatedAtModel):
    origin_store = models.ForeignKey(
        Store, related_name="distributions_from", on_delete=models.CASCADE
    )
    destination_store = models.ForeignKey(
        Store, related_name="distributions_to", on_delete=models.CASCADE
    )
    transfer_datetime = models.DateTimeField(null=True, blank=True)


    def __str__(self):
        return f"Distribución de {self.origin_store.get_full_name()} a {self.destination_store.get_full_name()}"

class Transfer(CreatedAtModel):
    distribution = models.ForeignKey(
        Distribution, related_name="transfers", on_delete=models.CASCADE, null=True, blank=True
    )
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
        return f"Transferencia de {self.quantity}x{self.product.name} de {self.origin_store.name} a {self.destination_store.name}"



class CashFlow(CreatedAtModel):
    TRANSACTION_TYPES_CHOICES = [
        ("E", "Entrada"),  # Entrada de dinero
        ("S", "Salida"),  # Salida de dinero
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    concept = models.CharField(max_length=50)
    transaction_type = models.CharField(max_length=1, choices=TRANSACTION_TYPES_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return ("{} {}").format(self.concept, self.store)

class StoreWorker(models.Model):
    ROLE_CHOICES = [
        ('A', 'Administrador'),
        ('V', 'Vendedor'),
    ]
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='workers')
    worker = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=1, choices=ROLE_CHOICES)

    def role_display(self):
        return self.get_role_display()