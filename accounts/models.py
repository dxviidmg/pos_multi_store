from django.db import models
from django.contrib.auth.models import User
from tenants.models import Tenant
from products.models import Store


#class Profile(models.Model):
#    user = models.ForeignKey(User, on_delete=models.CASCADE)
#    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)



def get_full_name(self):
    return "{} {}".format(self.first_name, self.last_name)

#def get_tenant(self):
#    return Profile.objects.get(user=self).tenant.pk

def get_tenant(self):
    return Tenant.objects.filter(owner=self).first()

def get_store(self):
    return Store.objects.filter(manager=self).first()

User.add_to_class("__str__", get_full_name)
User.add_to_class("get_tenant", get_tenant)
User.add_to_class("get_store", get_store)

