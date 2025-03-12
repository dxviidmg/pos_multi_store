from sales.models import Sale, ProductSale
from datetime import date
from products.models import StoreProduct

def run():
    today = date.today()
    sales = Sale.objects.filter(created_at__date=today)

    ids = []
    for sale in sales:
        products_sales = ProductSale.objects.filter(sale=sale).select_related('product')
        for product_sale in products_sales:
            if product_sale.price != product_sale.product.unit_price:
                sp1 = list(StoreProduct.objects.filter(product=product_sale.product)
                           .values_list('id', flat=True))
                ids += sp1
                
                sp2 = list(StoreProduct.objects.filter(
                    store=sale.store,
                    product__id__in=sp1
                ).values_list('id', flat=True))
                ids += sp2

    ids = set(ids)
    print(ids)


