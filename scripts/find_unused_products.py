"""
Compara productos de un archivo Excel contra la BD y detecta los que nunca
han tenido ventas, transferencias ni logs (productos sin uso).
Uso: python manage.py runscript find_unused_products
"""
import openpyxl
from products.models import Product, Transfer
from sales.models import ProductSale
from logs.models import StoreProductLog

TENANT_SHORT_NAME = "pdbj"
EXCEL_PATH = "scripts/data/pdbj/Productos 0 SAID.xlsx"


def run():
    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb.active
    codes = [str(row[0]) for row in ws.iter_rows(min_row=2, values_only=True) if row[0]]

    excel_codes = set(codes)
    all_tenant_codes = set(Product.objects.filter(brand__tenant__short_name=TENANT_SHORT_NAME).values_list("code", flat=True))

    only_in_excel = excel_codes - all_tenant_codes
    only_in_db = all_tenant_codes - excel_codes

    print(f"Total en Excel: {len(excel_codes)}")
    print(f"Total en BD (tenant): {len(all_tenant_codes)}")

    if only_in_excel:
        print(f"\n--- En Excel pero NO en BD ({len(only_in_excel)}) ---")
        for c in sorted(only_in_excel):
            print(c)

    if only_in_db:
        print(f"\n--- En BD pero NO en Excel ({len(only_in_db)}) ---")
        for c in sorted(only_in_db):
            print(c)

    if not only_in_excel and not only_in_db:
        print("\nNo hay diferencias entre Excel y BD.")

    # --- Productos nunca utilizados ---
    products = Product.objects.filter(brand__tenant__short_name=TENANT_SHORT_NAME, code__in=codes)

    sold_ids = set(ProductSale.objects.filter(product__in=products).values_list("product_id", flat=True))
    transferred_ids = set(Transfer.objects.filter(product__in=products).values_list("product_id", flat=True))
    logged_ids = set(StoreProductLog.objects.filter(store_product__product__in=products).values_list("store_product__product_id", flat=True))
    used_ids = sold_ids | transferred_ids | logged_ids

    unused = products.exclude(id__in=used_ids).order_by("code")

    print(f"\nEncontrados en BD (del Excel): {products.count()}")
    print(f"Con ventas: {len(sold_ids)}")
    print(f"Con transferencias: {len(transferred_ids)}")
    print(f"Con logs: {len(logged_ids)}")
    print(f"Nunca utilizados: {unused.count()}\n")

    no_sales = products.exclude(id__in=sold_ids).order_by("code")
    print(f"--- Sin ventas ({no_sales.count()}) ---")
    for p in no_sales:
        print(f"{p.code} | {p.get_description()}")

    print(f"\n--- Nunca utilizados ({unused.count()}) ---")

    for p in unused:
        print(f"{p.code} | {p.get_description()}")

    # deleted_count, _ = unused.delete()
    # print(f"\nEliminados: {deleted_count} registros (productos + relaciones en cascada)")
