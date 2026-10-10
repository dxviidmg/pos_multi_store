"""
Script para crear o actualizar marcas desde una lista de especificaciones.
También asigna las marcas a productos existentes que tengan el nombre de la marca.
Maneja mayúsculas, minúsculas y acentos.

Uso:
    python manage.py shell < scripts/create_brands.py
"""

from products.models import Brand, Product
from tenants.models import Tenant
from django.db.models import Q
import unicodedata

def normalize_text(text):
    """Normaliza texto: elimina acentos y convierte a minúsculas"""
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn').lower().strip()

def find_brand_in_text(brand_name, text):
    """Busca la marca en el texto ignorando acentos y mayúsculas"""
    brand_normalized = normalize_text(brand_name)
    text_normalized = normalize_text(text)
    return brand_normalized in text_normalized

# Obtener el tenant (usa el short_name 'jh' del contexto proporcionado)
try:
    tenant = Tenant.objects.get(short_name='jh')
    print(f"✓ Tenant encontrado: {tenant.name}")
except Tenant.DoesNotExist:
    print("✗ Error: Tenant con short_name 'jh' no existe. Verifica tus datos.")
    exit(1)

# Definición de marcas por categoría
brands_data = {
    "Cosméticos": [
        "Bissú",
        "Italia Deluxe",
        "Pink Up",
        "Saniye",
        "Prosa",
        "By Apple",
        "Beauty Creations",
        "Yuya",
        "Huxia Beauty",
        "Hedy Beauty",
        "Meliya Beauty",
        "Kiss",
    ],
    "Papelería": [
        "Politec",
        "Crayola",
        "Vinci",
        "Scribe",
        "Norma",
        "Maped",
        "Azor",
        "Dixon",
        "Sharpie",
        "Pritt",
        "Prismacolor",
    ],
    "Mochilas": [
        "Ruz",
        "Lluvia",
        "Nicks Club",
        "X-Gear",
        "Chenson",
        "Coach",
        "Jansport",
        "Nike",
        "Puma",
    ],
    "Otras": [
        "Golden Kids",
        "Doms",
        "Decorator",
        "Selecto",
        "Kams",
        "Krepe",
    ],
}

# Procesar todas las marcas
total_created = 0
total_updated = 0
total_products_assigned = 0

for category, brands_list in brands_data.items():
    print(f"\n📁 Categoría: {category}")
    for brand_name in brands_list:
        brand, created = Brand.objects.get_or_create(
            name=brand_name,
            tenant=tenant,
        )
        if created:
            print(f"  ✓ Creada: {brand_name}")
            total_created += 1
        else:
            print(f"  ↻ Actualizada: {brand_name}")
            total_updated += 1
        
        # Obtener todos los productos del tenant
        all_products = Product.objects.filter(brand__tenant=tenant)
        
        # Buscar productos que contengan la marca (con normalización)
        products_to_update = []
        for product in all_products:
            if find_brand_in_text(brand_name, product.name) and product.brand != brand:
                products_to_update.append(product)
        
        # Actualizar los productos encontrados
        if products_to_update:
            product_ids = [p.id for p in products_to_update]
            updated_count = Product.objects.filter(id__in=product_ids).update(brand=brand)
            print(f"    → {updated_count} producto(s) actualizado(s) con la marca {brand_name}")
            total_products_assigned += updated_count

# Resumen final
print(f"\n{'='*60}")
print(f"📊 RESUMEN DE OPERACIÓN")
print(f"{'='*60}")
print(f"✓ Marcas creadas:             {total_created}")
print(f"↻ Marcas actualizadas:        {total_updated}")
print(f"📦 Total de marcas procesadas: {total_created + total_updated}")
print(f"🔗 Productos asignados:       {total_products_assigned}")
print(f"{'='*60}")

# Verificar marcas en la BD
existing_brands = Brand.objects.filter(tenant=tenant).count()
print(f"\n📋 Total de marcas en BD para el tenant '{tenant.name}': {existing_brands}")

# Mostrar resumen de productos por marca
print(f"\n📊 RESUMEN DE PRODUCTOS POR MARCA")
print(f"{'='*60}")
for category, brands_list in brands_data.items():
    print(f"\n{category}:")
    for brand_name in brands_list:
        brand = Brand.objects.get(name=brand_name, tenant=tenant)
        product_count = brand.products.count()
        print(f"  {brand_name}: {product_count} productos")
