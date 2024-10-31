from products.models import Store, Product, Brand, StoreProduct
from django.contrib.auth.models import User
import xlrd
from decimal import Decimal


class DeleteProductManager:
    def delete_products(self):
        p = Product.objects.all()
        p.delete()

def run():
    product_manager = DeleteProductManager()
    product_manager.delete_products()
