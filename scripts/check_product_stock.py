from tenants.models import Tenant
from products.models import Product, StoreProduct
from django.db.models import Count
from logs.models import StoreProductLog
from tqdm import tqdm

def run():
        sps = StoreProduct.objects.all()

        sps = sps[46862:]

        for sp in tqdm(sps, desc="Procesando", unit="Log"):
            spl = StoreProductLog.objects.filter(store_product=sp).order_by('id').last()

            if not spl:
                continue
            
            if sp.stock == spl.updated_stock or sp.stock > 0:
                continue
            print(sp.product.code, sp.store, sp.stock, spl.updated_stock)