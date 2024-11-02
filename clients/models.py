from django.db import models
from products.models import Base
from django.core.validators import MinValueValidator, MaxValueValidator


class Discount(models.Model):

    discount_percentage = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], unique=True)

    def __str__(self):
        return '{}%'.format(self.discount_percentage)

    def get_discount_percentage_complement(self):
        return 100 - self.discount_percentage

class Client(models.Model):
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE)   
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=10)


    def get_full_name(self):
        return '{} {}'.format(self.first_name, self.last_name)

    def __str__(self):
        return self.get_full_name()
    



