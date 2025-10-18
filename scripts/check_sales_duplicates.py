from sales.models import Sale
from products.models import StoreProduct
from tqdm import tqdm
from django.utils.timezone import now
from datetime import timedelta



def run():
    today = now().date()

#    for day in range(30):
#        yesterday = now().date() - timedelta(days=day)
#        sales = Sale.objects.filter(created_at__date=yesterday)
#        print(sales.count())

#Correr en casa
    sales = Sale.objects.filter(created_at__date__gte="2025-10-01")#[22260:]
    
    for sale in tqdm(sales, desc="check sales", unit="Sale"):
        if sale.is_duplicate():
            print(sale, sale.store)
