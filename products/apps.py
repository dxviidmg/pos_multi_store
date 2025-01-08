from django.apps import AppConfig
from django.db.models.signals import post_save


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'


    def ready(self):
        from .models import Product, Store
        from .signals import create_product_in_stores, create_products_in_store

        post_save.connect(create_product_in_stores, sender=Product)
        post_save.connect(create_products_in_store, sender=Store)