"""
Script para transferir ventas de una tienda a otra
Uso: python manage.py runscript transfer_sales
"""
from sales.models import Sale
from products.models import Store


def run():
    stores = Store.objects.all().order_by('name')
    
    print("\n=== TIENDAS DISPONIBLES ===")
    for store in stores:
        print(f"{store.id}: {store.get_full_name()}")
    
    try:
        origin_id = int(input("\nID de tienda origen: "))
        destination_id = int(input("ID de tienda destino: "))
        
        origin = Store.objects.get(id=origin_id)
        destination = Store.objects.get(id=destination_id)
        
        sales_count = Sale.objects.filter(store_id=origin_id).count()
        
        print(f"\n¿Transferir {sales_count} ventas de '{origin.get_full_name()}' a '{destination.get_full_name()}'?")
        confirm = input("Escribir 'SI' para confirmar: ")
        
        if confirm == "SI":
            updated = Sale.objects.filter(store_id=origin_id).update(store_id=destination_id)
            print(f"\n✓ {updated} ventas transferidas exitosamente")
        else:
            print("\nOperación cancelada")
            
    except Store.DoesNotExist:
        print("\n✗ Error: Tienda no encontrada")
    except ValueError:
        print("\n✗ Error: ID inválido")
    except Exception as e:
        print(f"\n✗ Error: {e}")
