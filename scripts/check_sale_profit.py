"""
Script para verificar el profit de una venta específica.
Uso: python manage.py runscript check_sale_profit
"""
from decimal import Decimal
from django.db.models import F, Sum, DecimalField
from sales.models import Sale, ProductSale


def run():
    """Muestra el cálculo detallado del profit de una venta"""
    
    sale_id = input("Ingresa el ID de la venta: ").strip()
    
    try:
        sale = Sale.objects.prefetch_related('products_sale__product').get(id=sale_id)
    except Sale.DoesNotExist:
        print(f"\n❌ Venta {sale_id} no encontrada")
        return
    
    print(f"\n{'='*60}")
    print(f"Venta ID: {sale.id}")
    print(f"Fecha: {sale.created_at.strftime('%Y-%m-%d %H:%M')}")
    print(f"Total: ${sale.total}")
    print(f"Profit guardado: ${sale.profit}")
    print(f"{'='*60}\n")
    
    print(f"{'Producto':<30} {'Cant.':>8} {'Precio':>10} {'Costo':>10} {'Profit':>12}")
    print("-" * 72)
    
    total_profit = Decimal('0.00')
    
    for ps in sale.products_sale.all():
        product_name = ps.product.name[:28] if ps.product.name else str(ps.product.id)
        quantity = ps.quantity
        price = ps.price
        cost = ps.product.cost if ps.product.cost else Decimal('0.00')
        profit = (price - cost) * quantity
        
        total_profit += profit
        
        print(f"{product_name:<30} {quantity:>8} ${price:>9} ${cost:>9} ${profit:>11}")
    
    print("-" * 72)
    print(f"{'TOTAL PROFIT (calculado)':<60} ${total_profit:>11}")
    print(f"{'Profit según get_profit()':<60} ${sale.get_profit():>11}")
    print(f"{'Profit guardado en BD':<60} ${sale.profit:>11}")
    
    if sale.profit == total_profit:
        print(f"\n✅ Profit correcto")
    else:
        print(f"\n⚠️  Discrepancia detectada")
