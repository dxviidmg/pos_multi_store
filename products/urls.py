from rest_framework.routers import DefaultRouter
from .views import StoreProductViewSet, ProductTransferViewSet

app_name = 'products'

router = DefaultRouter() 
router.register('store-product', StoreProductViewSet, basename='store-product')
router.register('product-transfer', ProductTransferViewSet, basename='product-transfer')
urlpatterns = router.urls