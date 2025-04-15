from tenants.models import Tenant
from products.models import Product, StoreProductLog
from django.db.models import Count


def run():
    tenants = Tenant.objects.all()

    for index, tenant in enumerate(tenants):
        print(tenant)
        if index == 0:
            continue

        products = Product.objects.filter(brand__tenant=tenant)

        for product in products:
            stock = product.get_stock()

            if stock != 0:
                continue

            spl_count = StoreProductLog.objects.filter(
                store_product__product=product
            ).count()

            if spl_count == 0:
                print(product.code)