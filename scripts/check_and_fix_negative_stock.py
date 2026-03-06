"""
Script para revisar y corregir stock negativo
Uso: python manage.py runscript check_and_fix_negative_stock --script-args --fix
"""
from products.models import StoreProduct
import sys


def run(*args):
    """
    Revisa y corrige stock negativo en productos
    
    Args:
        --fix: Corregir stock negativo (sin esto solo muestra)
    """
    fix = '--fix' in args
    
    negative_stock = StoreProduct.objects.filter(stock__lt=0).select_related(
        'product', 'store'
    )
    
    count = negative_stock.count()
    
    if count == 0:
        print("✅ No hay productos con stock negativo")
        return
    
    print(f"⚠️  Productos con stock negativo: {count}")
    
    for sp in negative_stock:
        print(f"  - {sp.product.code} ({sp.product.name}) en {sp.store.name}: stock={sp.stock}")
        
        if fix:
            sp.stock = 0
            sp.save()
            print(f"    ✓ Ajustado a 0")
    
    if not fix:
        print(f"\n⚠️  Usa --script-args --fix para corregir {count} producto(s)")
    else:
        print(f"\n✅ {count} producto(s) corregido(s)")

