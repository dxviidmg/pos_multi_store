"""
Script para calcular y actualizar el campo profit en todas las ventas existentes.
Uso: python manage.py runscript backfill_sale_profit
"""
from decimal import Decimal
from django.db.models import F, Sum, DecimalField
from sales.models import Sale


def run():
    """Calcula y actualiza el profit para todas las ventas"""
    
    total_sales = Sale.objects.count()
    print(f"Total de ventas a procesar: {total_sales}")
    
    # Procesar en chunks para no sobrecargar memoria
    chunk_size = 100
    updated_count = 0
    errors = []
    
    sales = Sale.objects.all()
    
    for i in range(0, total_sales, chunk_size):
        chunk = sales[i:i + chunk_size]
        
        for sale in chunk:
            try:
                # Calcular profit igual que en get_profit()
                result = sale.products_sale.aggregate(
                    total=Sum(
                        (F('price') - F('product__cost')) * F('quantity'),
                        output_field=DecimalField()
                    )
                )
                profit = result['total'] or Decimal('0.00')
                
                # Actualizar solo si cambió
                if sale.profit != profit:
                    sale.profit = profit
                    sale.save(update_fields=['profit'])
                    updated_count += 1
                
            except Exception as e:
                errors.append(f"Error en venta {sale.id}: {str(e)}")
        
        # Mostrar progreso
        processed = min(i + chunk_size, total_sales)
        print(f"Procesadas {processed}/{total_sales} ventas ({updated_count} actualizadas)")
    
    print(f"\n✅ Backfill completado")
    print(f"   Total de ventas: {total_sales}")
    print(f"   Actualizadas: {updated_count}")
    
    if errors:
        print(f"\n⚠️  Errores encontrados ({len(errors)}):")
        for error in errors[:10]:  # Mostrar solo los primeros 10
            print(f"   - {error}")
        if len(errors) > 10:
            print(f"   ... y {len(errors) - 10} errores más")
