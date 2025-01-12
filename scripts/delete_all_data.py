from products.models import Store, Product, Brand, StoreProduct
from django.contrib.auth.models import User
import xlrd
from decimal import Decimal


class DeleteStoreManager:
    def delete_stores(self):
        s = Store.objects.all()
        s.delete()

class DeleteProductManager:
    def delete_products(self):
        p = Product.objects.all()
        p.delete()

def run():
#    store_manager = DeleteStoreManager()
#    store_manager.delete_stores()

    product_manager = DeleteProductManager()
    product_manager.delete_products()
