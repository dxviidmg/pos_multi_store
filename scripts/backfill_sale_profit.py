"""
Script para calcular y actualizar el campo profit en todas las ventas existentes.
Uso: python manage.py runscript backfill_sale_profit

Nota: Script one-time para poblar profit histórico. Ignora ventas canceladas.
"""
from django.db import connection
from sales.models import Sale


def run():
    """Calcula y actualiza el profit para ventas no canceladas con profit = 0"""
    
    # Filtrar solo ventas no canceladas con profit = 0
    total_sales = Sale.objects.filter(is_canceled=False, profit=0).count()
    print(f"Total de ventas a procesar (profit=0, excluyendo canceladas): {total_sales}")
    
    if total_sales == 0:
        print("No hay ventas para procesar.")
        return
    
    updated_count = 0
    errors = []
    processed = 0
    
    # Procesar en batches para evitar cursor closed
    batch_size = 1000
    offset = 0
    
    while offset < total_sales:
        # Cerrar conexión vieja antes de cada batch
        connection.close()
        
        # Obtener batch de ventas
        sale_ids = list(
            Sale.objects.filter(is_canceled=False, profit=0)
            .order_by('id')
            .values_list('id', flat=True)[offset:offset + batch_size]
        )
        
        if not sale_ids:
            break
        
        # Procesar cada venta del batch
        for sale_id in sale_ids:
            processed += 1
            try:
                sale = Sale.objects.prefetch_related('products_sale__product').get(id=sale_id)
                
                # Usar el método get_profit() del modelo
                profit = sale.get_profit()
                
                # Actualizar solo si cambió
                if sale.profit != profit:
                    sale.profit = profit
                    sale.save(update_fields=['profit'])
                    updated_count += 1
                
            except Exception as e:
                errors.append(f"Error en venta {sale_id}: {str(e)}")
        
        # Mostrar progreso
        print(f"Procesadas {processed}/{total_sales} ventas ({updated_count} actualizadas)")
        
        offset += batch_size
    
    print(f"\n✅ Backfill completado")
    print(f"   Total de ventas procesadas: {processed}")
    print(f"   Actualizadas: {updated_count}")
    
    if errors:
        print(f"\n⚠️  Errores encontrados ({len(errors)}):")
        for error in errors[:10]:
            print(f"   - {error}")
        if len(errors) - 10 > 0:
            print(f"   ... y {len(errors) - 10} errores más")
