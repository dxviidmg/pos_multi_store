from django.db import models
from django.contrib.auth.models import User
from tenants.models import Tenant
from products.models import Store


def get_full_name(self):
    return f"{self.first_name} {self.last_name}"

def get_store(self):
    return Store.objects.filter(manager=self).first()

def get_tenant(self):
    # Usar `or` para evitar realizar múltiples consultas
    return Tenant.objects.filter(owner=self).first() or self.get_store().tenant

def is_owner(self):
    # Devolver directamente la evaluación booleana de la consulta
    return Tenant.objects.filter(owner=self).exists()

# Asignar métodos a la clase `User`
User.add_to_class("__str__", get_full_name)
User.add_to_class("get_store", get_store)
User.add_to_class("get_tenant", get_tenant)
User.add_to_class("is_owner", is_owner)
