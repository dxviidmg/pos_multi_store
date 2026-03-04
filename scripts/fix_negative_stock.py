"""
Script para corregir stock negativo antes de aplicar constraint
"""
from products.models import StoreProduct

def run():
    # Encontrar productos con stock negativo
    negative_stock = StoreProduct.objects.filter(stock__lt=0)
    
    print(f"Productos con stock negativo: {negative_stock.count()}")
    
    for sp in negative_stock:
        print(f"  - {sp.product.code} ({sp.product.name}) en {sp.store.name}: stock={sp.stock}")
        # Ajustar a 0
        sp.stock = 0
        sp.save()
        print(f"    ✓ Ajustado a 0")
    
    print("\n✅ Stock negativo corregido")
