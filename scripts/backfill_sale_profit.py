"""
Script para calcular y actualizar el campo profit en todas las ventas existentes.
Uso: python manage.py runscript backfill_sale_profit

Nota: Script one-time para poblar profit histórico. Ignora ventas canceladas.
"""
from django.db.models import F, Sum, DecimalField, Prefetch
from sales.models import Sale, ProductSale


def run():
    """Calcula y actualiza el profit para todas las ventas no canceladas"""
    
    # Filtrar solo ventas no canceladas
    total_sales = Sale.objects.filter(is_canceled=False).count()
    print(f"Total de ventas a procesar (excluyendo canceladas): {total_sales}")
    
    if total_sales == 0:
        print("No hay ventas para procesar.")
        return
    
    updated_count = 0
    errors = []
    
    # Usar iterator() con prefetch para reducir N+1 queries
    sales = Sale.objects.filter(is_canceled=False).prefetch_related(
        Prefetch(
            'products_sale',
            queryset=ProductSale.objects.select_related('product')
        )
    ).iterator(chunk_size=500)
    
    processed = 0
    
    for sale in sales:
        processed += 1
        try:
            # Calcular profit usando la lógica de get_profit()
            result = sale.products_sale.aggregate(
                total=Sum(
                    (F('price') - F('product__cost')) * F('quantity'),
                    output_field=DecimalField()
                )
            )
            profit = result['total'] or 0
            
            # Actualizar solo si cambió
            if sale.profit != profit:
                sale.profit = profit
                sale.save(update_fields=['profit'])
                updated_count += 1
            
        except Exception as e:
            errors.append(f"Error en venta {sale.id}: {str(e)}")
        
        # Mostrar progreso cada 500 ventas
        if processed % 500 == 0:
            print(f"Procesadas {processed}/{total_sales} ventas ({updated_count} actualizadas)")
    
    print(f"\n✅ Backfill completado")
    print(f"   Total de ventas procesadas: {processed}")
    print(f"   Actualizadas: {updated_count}")
    
    if errors:
        print(f"\n⚠️  Errores encontrados ({len(errors)}):")
        for error in errors[:10]:
            print(f"   - {error}")
        if len(errors) > 10:
            print(f"   ... y {len(errors) - 10} errores más")
