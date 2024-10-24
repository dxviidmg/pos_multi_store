from django.db import models


class Sale(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
#    client_name = models.CharField(max_length=255)