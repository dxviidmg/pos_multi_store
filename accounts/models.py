from django.contrib.auth.models import User
from tenants.models import Tenant
from products.models import Store, StoreWorker


def get_full_name(self):
    return f"{self.first_name} {self.last_name}"

def get_store(self):
    return getattr(StoreWorker.objects.filter(worker=self).first(), "store", None) or Store.objects.filter(manager=self).first()
    

def get_role(self):
    if Tenant.objects.filter(owner=self).first():
        return 'owner'
    if Store.objects.filter(manager=self).first():
        return 'manager'
    if StoreWorker.objects.filter(worker=self).first():
        return 'seller'
    return 'Sin definir'

def get_tenant(self):
    # Usar `or` para evitar realizar múltiples consultas
    return Tenant.objects.filter(owner=self).first() or self.get_store().tenant

# Asignar métodos a la clase `User`
User.add_to_class("__str__", get_full_name)
User.add_to_class("get_store", get_store)
User.add_to_class("get_tenant", get_tenant)
User.add_to_class("get_role", get_role)
