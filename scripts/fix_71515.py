from sales.models import ProductSale, Sale
from clients.models import Client


def run():
    sale = Sale.objects.get(id=71515)

    products_sale = sale.products_sale.all()
    total = 0
    for product_sale in products_sale:
        total += product_sale.get_total()
    
    sale.total = round(total)
    sale.save()


