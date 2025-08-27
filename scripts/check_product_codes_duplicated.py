from tenants.models import Tenant
from products.models import Product
from django.db.models import Count


def run():
    tenants = Tenant.objects.all()

    for index, tenant in enumerate(tenants):

#        if index == 0:
#            continue

        products = Product.objects.filter(brand__tenant=tenant)
        print('tenant', tenant.name)
        print(products.count())
        print(products.values_list('code').distinct().count())

        repeated_codes = products.values('code').annotate(code_count=Count('code')).filter(code_count__gt=1)

        for item in repeated_codes:
            print(f"Code: {item['code']} - Count: {item['code_count']}")