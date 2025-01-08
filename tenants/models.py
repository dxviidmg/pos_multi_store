from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.utils.text import slugify


class Tenant(models.Model):
    name = models.CharField(max_length=100)
    domain = models.CharField(max_length=100, unique=True, blank=True)  # Dominio único para identificar el tenant
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    

    def __str__(self):
        return self.name
    

    def save(self, *args, **kwargs):
        if not self.pk:  # Solo para nuevos objetos
            # Generar el dominio en formato slug
            self.domain = self.name.replace(' ', '_').lower()

            # Crear un username y nombre para el propietario
            username = f"owner_{self.domain}"
            first_name = username.replace('_', ' ').title()

            # Crear o recuperar al usuario propietario
            self.owner, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'password': make_password(username),
                },
            )

        super().save(*args, **kwargs)