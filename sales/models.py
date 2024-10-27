from django.db import models
from django.contrib.auth.models import User


class Sale(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    saler = models.ForeignKey(User, on_delete=models.CASCADE)