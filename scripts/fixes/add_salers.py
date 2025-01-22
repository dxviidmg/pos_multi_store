from sales.models import Sale

def run():
    sales = Sale.objects.filter(saler=None)
    for sale in sales:
        sale.saler = sale.store.manager
        sale.save()