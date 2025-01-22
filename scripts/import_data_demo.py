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
        {"name": "Principal", "store_type": "T"},
        {"name": "Secundaria", "store_type": "T"},
        {"name": "Almacen", "store_type": "A"},
    ]

    data_products = [
        {
            "brand": "Aguas Inc",
            "code": "1",
            "name": "Agua embotellada (1 L)",
            "purchase_price": 5.00,
            "unit_sale_price": 10.00,
            "wholesale_sale_price": 8.00,
            "min_wholesale_quantity": 5,
            "apply_wholesale_price_on_client_discount": False,
        },
        {
            "brand": "Aguas Inc",
            "code": "2",
            "name": "Agua embotellada (2 L)",
            "purchase_price": 8.00,
            "unit_sale_price": 15.00,
            "wholesale_sale_price": 12.00,
            "min_wholesale_quantity": 5,
            "apply_wholesale_price_on_client_discount": True,
        },
        {
            "brand": "Refrescos Inc",
            "code": "3",
            "name": "Refresco cola (1L)",
            "purchase_price": 10.00,
            "unit_sale_price": 15.50,
            "wholesale_sale_price": None,
            "min_wholesale_quantity": None,
            "apply_wholesale_price_on_client_discount": False,
        },
        {
            "brand": "Refrescos Inc",
            "code": "4",
            "name": "Refresco cola (2L)",
            "purchase_price": 15.00,
            "unit_sale_price": 20.00,
            "wholesale_sale_price": None,
            "min_wholesale_quantity": None,
            "apply_wholesale_price_on_client_discount": False,
        },
        {
            "brand": "Jugos Inc",
            "code": "5",
            "name": "Jugo naranza (500ml)",
            "purchase_price": 12.00,
            "unit_sale_price": 16,
            "wholesale_sale_price": None,
            "min_wholesale_quantity": None,
            "apply_wholesale_price_on_client_discount": False,
        },
        {
            "brand": "Jugos Inc",
            "code": "6",
            "name": "Jugo naranza (1L)",
            "purchase_price": 20.00,
            "unit_sale_price": 25.00,
            "wholesale_sale_price": None,
            "min_wholesale_quantity": None,
            "apply_wholesale_price_on_client_discount": False,
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

    tenant_manager = TenantManager(data_tenant)
    tenant = tenant_manager.create_tenant()

    store_manager = StoreManager(tenant)
    product_manager = ProductManager(tenant)
    client_manager = ClientManager(tenant)

    # Ejecutar la creación de tiendas y productos
    store_manager.create_stores(data_stores)
    product_manager.create_demo_products(data_products)
    client_manager.create_demo_clients(data_clients)
