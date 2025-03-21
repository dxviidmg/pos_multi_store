from sales.models import Sale

def run():
    sales = Sale.objects.filter(seller=None)
    for sale in sales:
        sale.seller = sale.store.manager
        sale.save()