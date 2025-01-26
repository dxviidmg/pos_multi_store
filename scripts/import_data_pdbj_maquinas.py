from .managers import TenantManager, StoreManager, ProductManager


def run():
    """Función principal que será ejecutada por runscript"""

    data_tenant = {
        "name": "Productos de belleza Josue",
        "short_name": "pdbj",
        "stores": 5,
    }

    data_stores = [
        {"name": "Maquinas", "store_type": "T"}
    ]

    products_file_path = "scripts/data/pdbj/invmaquinas.xls"

    tenant_manager = TenantManager(data_tenant)
    tenant = tenant_manager.create_tenant()

    # Crear managers y ejecutar los procesos
    store_manager = StoreManager(tenant)
    product_manager = ProductManager(tenant)

    # Ejecutar la creación de tiendas y productos
    store_manager.create_stores(data_stores)
#    product_manager.validate_products_in_tenant_from_eleventa(products_file_path)
    product_manager.create_products_from_eleventa(products_file_path)
    product_manager.update_stock_by_store_from_eleventa(products_file_path, tenant, data_stores[0])