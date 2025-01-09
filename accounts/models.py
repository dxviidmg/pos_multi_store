from django.db import models
from django.contrib.auth.models import User
from tenants.models import Tenant
from products.models import Store


def get_full_name(self):
    return "{} {}".format(self.first_name, self.last_name)


def get_store(self):
    return Store.objects.filter(manager=self).first()


def get_tenant(self):
    tenant = Tenant.objects.filter(owner=self).first()
    return tenant if tenant else self.get_store().tenant


User.add_to_class("__str__", get_full_name)
User.add_to_class("get_store", get_store)
User.add_to_class("get_tenant", get_tenant)
