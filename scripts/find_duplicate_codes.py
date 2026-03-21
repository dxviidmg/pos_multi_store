"""
Busca productos con códigos duplicados dentro de un tenant y muestra su stock.
Uso: python manage.py runscript find_duplicate_codes
"""
from django.db.models import Count
from products.models import Product

TENANT_SHORT_NAME = "pdbj"


def run():
    duplicates = (
        Product.objects.filter(brand__tenant__short_name=TENANT_SHORT_NAME)
        .values("code")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )

    if not duplicates:
        print("No hay códigos duplicados.")
        return

    print(f"Códigos duplicados encontrados: {duplicates.count()}\n")

    for dup in duplicates:
        print(f"Código: {dup['code']} (x{dup['total']})")
        products = Product.objects.filter(
            brand__tenant__short_name=TENANT_SHORT_NAME, code=dup["code"]
        ).order_by("id")
        for p in products:
            stock = p.get_stock()
            print(f"  id={p.id} | {p.get_description()} | stock total: {stock}")
        print()
