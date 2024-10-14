from django.contrib import admin
from .models import SpecialClientType, SpecialClient


class SpecialClientTypeAdmin(admin.ModelAdmin):
    pass


admin.site.register(SpecialClientType, SpecialClientTypeAdmin)

class SpecialClientAdmin(admin.ModelAdmin):
    pass


admin.site.register(SpecialClient, SpecialClientAdmin)