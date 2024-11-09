from rest_framework.routers import DefaultRouter
from .views import StoreProductViewSet, ProductViewSet, ProductTransferViewSet, StoreViewSet, ConfirmProductTransfers, BrandViewSet
from django.urls import path

app_name = 'products'

router = DefaultRouter() 
router.register('store', StoreViewSet, basename='store')
router.register('brand', BrandViewSet, basename='brand')
router.register('product', ProductViewSet, basename='product')
router.register('store-product', StoreProductViewSet, basename='store-product')

router.register('product-transfer', ProductTransferViewSet, basename='product-transfer')
urlpatterns = router.urls

urlpatterns += [
    path('confirm-transfers/', ConfirmProductTransfers.as_view(), name='confirm-transfers'),
]