"""
Signals para la aplicación sales.
Actualiza automáticamente el profit de una venta cuando cambian sus productos.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import ProductSale, Sale


@receiver(post_save, sender=ProductSale)
def update_sale_profit_on_product_save(sender, instance, **kwargs):
    """Actualiza el profit de la venta cuando se crea o modifica un ProductSale"""
    sale = instance.sale
    sale.profit = sale.get_profit()
    sale.save(update_fields=['profit'])


@receiver(post_delete, sender=ProductSale)
def update_sale_profit_on_product_delete(sender, instance, **kwargs):
    """Actualiza el profit de la venta cuando se elimina un ProductSale"""
    sale = instance.sale
    sale.profit = sale.get_profit()
    sale.save(update_fields=['profit'])
