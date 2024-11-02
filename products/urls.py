from rest_framework.routers import DefaultRouter
from .views import StoreProductViewSet, ProductTransferViewSet, StoreViewSet, ConfirmProductTransfer
from django.urls import path

app_name = 'products'

router = DefaultRouter() 
router.register('store', StoreViewSet, basename='store')
router.register('store-product', StoreProductViewSet, basename='store-product')
router.register('product-transfer', ProductTransferViewSet, basename='product-transfer')
urlpatterns = router.urls

urlpatterns += [
    path('confirm-transfer/', ConfirmProductTransfer.as_view(), name='confirm-transfer'),
]