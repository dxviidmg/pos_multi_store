from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, StoreProduct, Store


@receiver(post_save, sender=Product)
def create_product_in_stores(sender, instance, created, **kwargs):
    if created:
        # Obtener todas las tiendas del tenant del producto
        stores = Store.objects.filter(tenant=instance.brand.tenant)
        
        # Crear StoreProduct en masa
        store_products = [
            StoreProduct(store=store, product=instance) for store in stores
        ]
        StoreProduct.objects.bulk_create(store_products, ignore_conflicts=True)


@receiver(post_save, sender=Store)
def create_products_in_store(sender, instance, created, **kwargs):
    if created:
        # Obtener todos los productos del tenant de la tienda
        products = Product.objects.filter(brand__tenant=instance.tenant)
        
        # Crear StoreProduct en masa
        store_products = [
            StoreProduct(store=instance, product=product) for product in products
        ]
        StoreProduct.objects.bulk_create(store_products, ignore_conflicts=True)
