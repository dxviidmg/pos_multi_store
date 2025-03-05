from products.models import StoreProductLog


def run():
    StoreProductLog.objects.filter(movement='D').update(movement='DI')
    StoreProductLog.objects.filter(movement='T').update(movement='TR')
    StoreProductLog.objects.filter(movement='C').update(movement='DE')
    StoreProductLog.objects.filter(movement='V').update(movement='VE')