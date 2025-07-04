from django.db import models
from products.models import Base, Store

# Create your models here.

class Brand(Base):
    pass

class Printer(models.Model):
    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, related_name="brand"
    )
    model = models.CharField(max_length=10)
    font_height = models.IntegerField(default=20)

    def __str__(self):
        return '{} {} {}'.format(self.brand.name, self.model, self.font_height)
    
class StorePrinter(models.Model):
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="printer"
    )
    printer = models.ForeignKey(
        Printer, on_delete=models.CASCADE, related_name="store"
    )