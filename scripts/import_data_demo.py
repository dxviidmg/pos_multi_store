from .managers import TenantManager, StoreManager, ProductManager, ClientManager


def run():
    """Función principal que será ejecutada por runscript"""

    data_tenant = {
        "name": "Demo",
        "short_name": "demo",
        "stores": 3,
        "is_sandbox": True,
    }

    data_stores = [
        {"name": "Almacen", "store_type": "A"},
        {"name": "Principal", "store_type": "T"},
        {"name": "Secundaria", "store_type": "T"},
    ]

    data_products = [
        {
            "brand": "Aguas Inc",
            "code": "AE1L",
            "name": "Agua embotellada (1 L)",
            "purchase_price": 5.00,
            "unit_sale_price": 10.00,
            "wholesale_sale_price": 8.00,
            "min_wholesale_quantity": 5,
            "apply_wholesale_price_on_costumer_discount": False,
        },
        {
            "brand": "Aguas embotelladas",
            "code": "AE2L",
            "name": "Agua embotellada (2 L)",
            "purchase_price": 8.00,
            "unit_sale_price": 15.00,
            "wholesale_sale_price": 12.00,
            "min_wholesale_quantity": 5,
            "apply_wholesale_price_on_costumer_discount": True,
        },
        {
            "brand": "Refrescos Inc",
            "code": "RC1L",
            "name": "Refresco cola (1 L)",
            "purchase_price": 10.00,
            "unit_sale_price": 15.50,
            "wholesale_sale_price": None,
            "min_wholesale_quantity": None,
            "apply_wholesale_price_on_costumer_discount": False,
        },
        {
            "brand": "Refrescos Inc",
            "code": "RC2L",
            "name": "Refresco cola (2 L)",
            "purchase_price": 15.00,
            "unit_sale_price": 20.00,
            "wholesale_sale_price": None,
            "min_wholesale_quantity": None,
            "apply_wholesale_price_on_costumer_discount": False,
        },
    ]

    data_clients = [
        {
            "discount_percentage": 5,
            "first_name": "Juan",
            "last_name": "Perez",
            "phone_number": "9999999999",
        }
    ]

    tenant = TenantManager(data_tenant)
    tenant_instance = tenant.create_tenant()

    store_manager = StoreManager(tenant_instance)
    product_manager = ProductManager(tenant_instance)
    client_manager = ClientManager(tenant_instance)

    # Ejecutar la creación de tiendas y productos
    store_manager.create_stores(data_stores)
    product_manager.create_demo_products(data_products)
    client_manager.create_demo_clients(data_clients)
