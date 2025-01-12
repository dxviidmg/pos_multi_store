from django.contrib import admin
from .models import Tenant, Payment


admin.site.register(Tenant)
admin.site.register(Payment)