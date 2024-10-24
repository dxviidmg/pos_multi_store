from django.contrib import admin
from .models import Discount, Client


class DiscountAdmin(admin.ModelAdmin):
    pass


admin.site.register(Discount, DiscountAdmin)

class ClientAdmin(admin.ModelAdmin):
    pass


admin.site.register(Client, ClientAdmin)