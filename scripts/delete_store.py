"""
Script para eliminar una tienda y todos sus datos relacionados
Uso: python manage.py runscript delete_store
"""
from products.models import Store, StoreProduct, Transfer, Distribution, StoreWorker
from sales.models import Sale
from printers.models import StorePrinter
from logs.models import StoreProductLog


def run():
    stores = Store.objects.all().order_by('name')
    
    print("\n=== TIENDAS DISPONIBLES ===")
    for store in stores:
        print(f"{store.id}: {store.get_full_name()}")
    
    try:
        store_id = int(input("\nID de tienda a eliminar: "))
        store = Store.objects.get(id=store_id)
        
        # Contar registros relacionados
        sales_count = Sale.objects.filter(store_id=store_id).count()
        products_count = StoreProduct.objects.filter(store_id=store_id).count()
        workers_count = StoreWorker.objects.filter(store_id=store_id).count()
        transfers_from = Transfer.objects.filter(origin_store_id=store_id).count()
        transfers_to = Transfer.objects.filter(destination_store_id=store_id).count()
        dist_from = Distribution.objects.filter(origin_store_id=store_id).count()
        dist_to = Distribution.objects.filter(destination_store_id=store_id).count()
        printers_count = StorePrinter.objects.filter(store_id=store_id).count()
        logs_count = StoreProductLog.objects.filter(store_related_id=store_id).count()
        
        print(f"\n=== DATOS A ELIMINAR DE '{store.get_full_name()}' ===")
        print(f"- Ventas: {sales_count}")
        print(f"- Productos: {products_count}")
        print(f"- Trabajadores: {workers_count}")
        print(f"- Transferencias (origen): {transfers_from}")
        print(f"- Transferencias (destino): {transfers_to}")
        print(f"- Distribuciones (origen): {dist_from}")
        print(f"- Distribuciones (destino): {dist_to}")
        print(f"- Impresoras: {printers_count}")
        print(f"- Logs: {logs_count}")
        print(f"- Tienda: 1")
        
        confirm = input("\nEscribir 'ELIMINAR TODO' para confirmar: ")
        
        if confirm == "ELIMINAR TODO":
            Sale.objects.filter(store_id=store_id).delete()
            StoreProduct.objects.filter(store_id=store_id).delete()
            StoreWorker.objects.filter(store_id=store_id).delete()
            Transfer.objects.filter(origin_store_id=store_id).delete()
            Transfer.objects.filter(destination_store_id=store_id).delete()
            Distribution.objects.filter(origin_store_id=store_id).delete()
            Distribution.objects.filter(destination_store_id=store_id).delete()
            StorePrinter.objects.filter(store_id=store_id).delete()
            StoreProductLog.objects.filter(store_related_id=store_id).delete()
            store.delete()
            
            print(f"\n✓ Tienda '{store.get_full_name()}' y todos sus datos eliminados exitosamente")
        else:
            print("\nOperación cancelada")
            
    except Store.DoesNotExist:
        print("\n✗ Error: Tienda no encontrada")
    except ValueError:
        print("\n✗ Error: ID inválido")
    except Exception as e:
        print(f"\n✗ Error: {e}")
