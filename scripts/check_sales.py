from sales.models import Sale, ProductSale
from datetime import date
from products.models import StoreProduct
from datetime import date, timedelta


def run():

    yesterday = date.today() - timedelta(days=1)
    sales = Sale.objects.filter(created_at__date=yesterday)

    ids = []
    for sale in sales:
        products_sales = ProductSale.objects.filter(sale=sale)
        for product_sale in products_sales:
            sp = StoreProduct.objects.filter(product=product_sale.product)
#                print('sp.pk', sp)
            sp1 = list(sp.values_list('id', flat=True))
            ids += sp1
            sp2 = StoreProduct.objects.filter(store=sale.store, product__id__in=sp)
            sp2 = list(sp2.values_list('id', flat=True))
            ids += sp2

    ids = set(ids)
    print(ids)


