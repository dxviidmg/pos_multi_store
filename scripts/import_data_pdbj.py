from .managers import TenantManager, StoreManager, ProductManager


def run():
    """Función principal que será ejecutada por runscript"""

    data_tenant = {
        "name": "Productos de belleza Josue",
        "short_name": "pdbj",
        "stores": 5,
    }

    data_stores = [
        {"name": "Zaragoza", "store_type": "T"},
        {"name": "1", "store_type": "A"},
    ]

    products_file_path = "scripts/import_data/pdbj/inventario.xls"

    tenant = TenantManager(data_tenant)
    tenant_instance = tenant.create_tenant()

    # Crear managers y ejecutar los procesos
    store_manager = StoreManager(tenant_instance)
    product_manager = ProductManager(tenant_instance)

    # Ejecutar la creación de tiendas y productos
    store_manager.create_stores(data_stores)
    product_manager.create_products_from_eleventa(products_file_path)
