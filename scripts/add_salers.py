from sales.models import Sale




#def get_store(self):
#    return Store.objects.filter(manager=self).first()
def run():
    sales = Sale.objects.filter(saler=None)
    for sale in sales:
        print(sale)
        print(sale.store.manager)
        sale.saler = sale.store.manager
        sale.save()
#        data = sp.__dict__
#        del data['_state']  

#        ProductSale.objects.get_or_create(**data)