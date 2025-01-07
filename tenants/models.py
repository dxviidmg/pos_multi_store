from django.db import models

class Tenant(models.Model):
    name = models.CharField(max_length=100)
    domain = models.CharField(max_length=100, unique=True)  # Dominio único para identificar el tenant

    def __str__(self):
        return self.name