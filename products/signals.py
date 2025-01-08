from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, StoreProduct, Store

@receiver(post_save, sender=Product)
def create_product_in_stores(sender, instance, created, **kwargs):
    
    if created:  # Solo se ejecuta cuando se crea un nuevo usuario
        stores = Store.objects.filter(tenant=instance.brand.tenant)
        for store in stores:
            StoreProduct.objects.get_or_create(store=store, product=instance)