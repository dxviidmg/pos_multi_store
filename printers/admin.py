from django.contrib import admin
from .models import Brand, Printer, StorePrinter

admin.site.register(Brand)
admin.site.register(Printer)
admin.site.register(StorePrinter)