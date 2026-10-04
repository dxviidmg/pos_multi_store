"""
Script para identificar ventas con profit igual o menor a 0.
Uso: python manage.py runscript check_zero_profit_sales
"""
from sales.models import Sale


def run():
    """Muestra las primeras 10 ventas con profit <= 0 en orden cronológico (excluye tenant demo)"""
    
    sales = Sale.objects.filter(
        profit__lte=0, is_canceled=False
    ).exclude(
        store__tenant__short_name='demo'
    ).select_related(
        'store', 'store__tenant'
    ).order_by('-created_at')[:50]
    
    total_count = Sale.objects.filter(profit__lte=0).exclude(store__tenant__short_name='demo').count()
    
    print(f"\n📊 Ventas con profit <= 0 (excluyendo demo): {total_count} en total\n")
    print("Primeras 10 en orden cronológico:\n")
    print(f"{'ID':<8} {'Fecha':<18} {'Tenant':<20} {'Tienda':<20} {'Profit':>12}")
    print("-" * 82)
    
    for sale in sales:
        tenant_name = sale.store.tenant.name[:18] if sale.store.tenant else "N/A"
        store_name = sale.store.name[:18] if sale.store.name else "N/A"
        print(f"{sale.id:<8} {sale.created_at.strftime('%Y-%m-%d %H:%M'):<18} {tenant_name:<20} {store_name:<20} {sale.profit:>12}")
