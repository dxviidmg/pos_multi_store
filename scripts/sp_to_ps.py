from sales.models import SaleProduct, ProductSale

def run():
    sps = SaleProduct.objects.all()
    for sp in sps:
        data = sp.__dict__
        del data['_state']  

        ProductSale.objects.get_or_create(**data)