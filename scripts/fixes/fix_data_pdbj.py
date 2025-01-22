from ..managers import TenantManager, ProductManager
from tqdm import tqdm
from products.models import Product

def run():
    """Función principal que será ejecutada por runscript"""

    data_tenant = {
        "name": "Productos de belleza Josue",
        "short_name": "pdbj",
        "stores": 5,
    }

    products_file_path = "scripts/import_data/pdbj/inventario.xls"

    tenant = TenantManager(data_tenant)
    tenant_instance = tenant.create_tenant()

    # Crear managers y ejecutar los procesos
    product_manager = ProductManager(tenant_instance)
    file = product_manager.read_file_from_eleventa(products_file_path)

    for row_idx in tqdm(
        range(1, file.nrows), desc="Updating Products", unit="product"
    ):
        row_values = file.row_values(row_idx)

        try:
            product = Product.objects.get(brand__tenant=tenant_instance, code=row_values[0])
        except Product.DoesNotExist:
            continue

        product.name = row_values[1]
        product.save()