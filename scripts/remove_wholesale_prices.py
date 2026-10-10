"""
Script para remover precios mayoreo y cantidad mínima mayoreo de productos con CMM=1.

Uso:
    ./manage_prod.py runscript remove_wholesale_prices
"""
from products.models import Product
from accounts.models import Tenant


def run():
    """Función ejecutada por django-extensions runscript"""
    tenant_shortname = input("Escribe el short_name del tenant: ").strip()

    if not tenant_shortname:
        print("❌ El short_name no puede estar vacío")
        return

    try:
        tenant = Tenant.objects.get(short_name=tenant_shortname)
    except Tenant.DoesNotExist:
        print(f"❌ Tenant con short_name '{tenant_shortname}' no existe")
        return

    products = Product.objects.filter(brand__tenant=tenant, min_wholesale_quantity=1)
    count = products.count()

    if count == 0:
        print(f"⚠️  No hay productos con CMM=1 en el tenant: {tenant.name}")
        return

    print(f"🔄 Removiendo precios mayoreo de {count} productos con CMM=1 del tenant: {tenant.name}")

    products.update(wholesale_price=None, min_wholesale_quantity=None)

    print(f"✅ Listo. Se removieron precios mayoreo de {count} productos")
