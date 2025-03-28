from sales.models import Sale, ProductSale
from datetime import date
from products.models import StoreProduct
from datetime import date, timedelta
import pandas as pd


def run():

    yesterday = date.today() - timedelta(days=1)
    sales = Sale.objects.filter(created_at__date=yesterday)

    ids = []
    for sale in sales:
        products_sales = ProductSale.objects.filter(sale=sale)
        for product_sale in products_sales:
            if product_sale.product.unit_price == product_sale.price:
                continue

            sp = StoreProduct.objects.filter(product=product_sale.product)

            sp1 = list(sp.values_list('id', flat=True))
            ids += sp1
            sp2 = StoreProduct.objects.filter(store=sale.store, product__id__in=sp)
            sp2 = list(sp2.values_list('id', flat=True))
            ids += sp2

    ids = set(ids)

    data = []
    for id in ids:
        sp = StoreProduct.objects.get(id=id)
        data += [{'tenant': sp.store.tenant.name, 'store': sp.store.name, 'code': sp.product.code, 'name': sp.product.name}]

    
    df = pd.DataFrame(data)

    c = '(precios incosistentes)'
    df.to_excel(f"Movimientos stock 11-03-2025 {c}.xlsx", index=False)



