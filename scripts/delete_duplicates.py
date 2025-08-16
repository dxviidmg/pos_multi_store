from sales.models import Sale
from products.models import StoreProduct
from tqdm import tqdm
from django.utils.timezone import now
from datetime import timedelta



def run():
    today = now().date()

    for day in range(30):
        yesterday = now().date() - timedelta(days=day)
        sales = Sale.objects.filter(created_at__date=yesterday)
        print(sales.count())

#Correr en casa
#    for sale in tqdm(sales, desc="delete sales", unit="Sale"):
#        sale.revert_stock_and_delete()
