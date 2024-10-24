from django.db import models
from django.contrib.auth.models import User

#traspasos, un vendedor hace traspasos, se crea, el registro de tienda a tienda, que fue y cuanto

class Base(models.Model):
    name = models.CharField(max_length=20)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name
    
class Brand(Base):
    pass

class Category(Base):
    pass

class Store(Base):
    manager = models.OneToOneField(User, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        # Guardar el producto primero
        super().save(*args, **kwargs)
        
        # Crear una entrada de StoreProduct para cada tienda
        products = Product.objects.all()
        for product in products:
            StoreProduct.objects.get_or_create(store=self, product=product)


class Product(Base):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    code = models.CharField(max_length=20, unique=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    public_sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    

    def save(self, *args, **kwargs):
        # Guardar el producto primero
        super().save(*args, **kwargs)
        
        # Crear una entrada de StoreProduct para cada tienda
        stores = Store.objects.all()
        for store in stores:
            StoreProduct.objects.get_or_create(store=store, product=self)



class StoreProduct(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    stock = models.PositiveIntegerField(default=0) 

    def __str__(self):
        return self.product.__str__() + " " + self.store.__str__()