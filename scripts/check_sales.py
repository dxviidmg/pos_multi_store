from sales.models import Sale, ProductSale
from datetime import date

def run():
    today = date.today() 
    sales = Sale.objects.filter(created_at__date=today)

    for sale in sales:
        products_sales = ProductSale.objects.filter(sale=sale)
        for product_sale in products_sales:
            if product_sale.price != product_sale.product.unit_price:
                print(sale.pk, sale.created_at.strftime('%H:%M:%S'), sale.store, product_sale.product.name, 'precio real', product_sale.price, 'precio puesto', product_sale.product.unit_price)

            


