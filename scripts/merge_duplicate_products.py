"""
Script para fusionar productos duplicados en un tenant.

Uso:
    ./manage_prod.py runscript merge_duplicate_products

El script:
1. Recibe el short_name del tenant
2. Recibe el código duplicado
3. Encuentra todos los productos con ese código
4. Migra todas las FKs del más reciente al más antiguo
5. Para stock, toma la cantidad mayor en cada tienda
6. Borra el producto duplicado
"""
from products.models import Product, StoreProduct
from accounts.models import Tenant
from django.apps import apps


def run():
    """Función ejecutada por django-extensions runscript"""
    # Input del usuario
    tenant_shortname = input("Escribe el short_name del tenant: ").strip()
    product_code = input("Escribe el código del producto duplicado: ").strip()

    if not tenant_shortname or not product_code:
        print("❌ El short_name y código no pueden estar vacíos")
        return

    # Validar tenant
    try:
        tenant = Tenant.objects.get(short_name=tenant_shortname)
    except Tenant.DoesNotExist:
        print(f"❌ Tenant con short_name '{tenant_shortname}' no existe")
        return

    # Buscar productos duplicados
    products = Product.objects.filter(
        code=product_code,
        brand__tenant=tenant
    ).order_by("id")

    if products.count() < 2:
        print(f"⚠️  No hay productos duplicados con código '{product_code}'")
        return

    if products.count() > 2:
        print(f"⚠️  Hay {products.count()} productos con este código. Solo manejamos 2.")
        return

    product_old = products[0]  # El más antiguo (primero)
    product_new = products[1]  # El más reciente (segundo)

    print(f"🔄 Fusionando productos:")
    print(f"   Antiguo (mantener): ID={product_old.id}, {product_old.name}")
    print(f"   Nuevo (borrar):     ID={product_new.id}, {product_new.name}")

    # Migrar todas las FKs
    migrate_foreign_keys(product_old, product_new)

    # Migrar stock (StoreProduct)
    migrate_stock(product_old, product_new)

    # Borrar el producto duplicado
    print(f"🗑️  Borrando producto ID={product_new.id}...")
    product_new.delete()

    print(f"✅ Fusión completada. Producto {product_new.id} eliminado.")


def migrate_foreign_keys(product_old, product_new):
    """Migra todas las FKs que apunten a product_new hacia product_old"""

    # Encontrar todos los modelos que tienen FK a Product
    for model in apps.get_models():
        for field in model._meta.get_fields():
            # Verificar si es una FK a Product
            if hasattr(field, 'related_model') and field.related_model == Product:
                if hasattr(field, 'name'):
                    # Construir el filtro dinámicamente
                    filter_key = f"{field.name}__exact"
                    try:
                        queryset = model.objects.filter(**{filter_key: product_new})
                        count = queryset.count()

                        if count > 0:
                            print(f"  → Migrando {count} registros de {model.__name__}.{field.name}")
                            update_key = field.name
                            queryset.update(**{update_key: product_old})
                    except Exception as e:
                        pass  # Ignorar errores en campos que no se puedan actualizar


def migrate_stock(product_old, product_new):
    """Migra stock, tomando la cantidad mayor en cada tienda"""

    # Obtener StoreProducts de ambos productos
    old_stocks = {sp.store_id: sp for sp in StoreProduct.objects.filter(product=product_old)}
    new_stocks = StoreProduct.objects.filter(product=product_new)

    for new_stock in new_stocks:
        store_id = new_stock.store_id

        if store_id in old_stocks:
            # Tienda existe en ambos: tomar el mayor
            old_stock = old_stocks[store_id]
            if new_stock.quantity > old_stock.quantity:
                print(f"  → Stock en tienda {new_stock.store.name}: actualizar a {new_stock.quantity}")
                old_stock.quantity = new_stock.quantity
                old_stock.save()
            new_stock.delete()
        else:
            # Tienda solo en new: migrar a old
            print(f"  → Stock en tienda {new_stock.store.name}: migrar {new_stock.quantity}")
            new_stock.product = product_old
            new_stock.save()
