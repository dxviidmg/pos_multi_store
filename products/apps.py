from django.apps import AppConfig
from django.db.models.signals import post_save


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'


    def ready(self):
        from .models import Product
        from .signals import create_product_in_stores

        post_save.connect(create_product_in_stores, sender=Product)