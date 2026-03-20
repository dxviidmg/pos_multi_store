"""
Fusiona productos duplicados (mismo código) en uno solo, reasignando ventas,
transferencias, logs y stock al producto principal. Elimina los duplicados.
Uso: python manage.py runscript merge_duplicate_product
"""
from products.models import Product, StoreProduct, Transfer
from sales.models import ProductSale
from logs.models import StoreProductLog

TENANT_SHORT_NAME = "pdbj"
CODE = "7502270290080"


def run():
    products = Product.objects.filter(brand__tenant__short_name=TENANT_SHORT_NAME, code=CODE).order_by("id")
    print(f"Productos encontrados: {products.count()}")
    for p in products:
        print(f"  id={p.id} | {p.get_description()}")

    if products.count() < 2:
        print("No hay duplicados.")
        return

    main = products.first()
    duplicates = products.exclude(id=main.id)
    dup_ids = list(duplicates.values_list("id", flat=True))

    print(f"\nProducto principal: id={main.id}")
    print(f"Duplicados a eliminar: {dup_ids}")

    # Reasignar ProductSale
    count = ProductSale.objects.filter(product_id__in=dup_ids).update(product=main)
    print(f"ProductSale reasignados: {count}")

    # Reasignar Transfer
    count = Transfer.objects.filter(product_id__in=dup_ids).update(product=main)
    print(f"Transfer reasignados: {count}")

    # Reasignar StoreProductLog -> va via StoreProduct
    main_store_products = {sp.store_id: sp for sp in StoreProduct.objects.filter(product=main)}

    for dup_sp in StoreProduct.objects.filter(product_id__in=dup_ids):
        if dup_sp.store_id in main_store_products:
            # Mover logs al StoreProduct del principal
            target_sp = main_store_products[dup_sp.store_id]
            count = StoreProductLog.objects.filter(store_product=dup_sp).update(store_product=target_sp)
            print(f"Logs movidos de StoreProduct {dup_sp.id} -> {target_sp.id}: {count}")
            # Sumar stock
            target_sp.stock += dup_sp.stock
            target_sp.save()
            print(f"Stock sumado a tienda {dup_sp.store.name}: +{dup_sp.stock}")
        else:
            # No existe StoreProduct en main, reasignar directamente
            dup_sp.product = main
            dup_sp.save()
            print(f"StoreProduct {dup_sp.id} reasignado al principal (tienda {dup_sp.store.name})")
            main_store_products[dup_sp.store_id] = dup_sp

    # Eliminar duplicados (cascade borra StoreProducts huérfanos)
    deleted_count, details = duplicates.delete()
    print(f"\nEliminados: {deleted_count} registros -> {details}")
