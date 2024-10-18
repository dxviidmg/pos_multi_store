from rest_framework.routers import DefaultRouter
from .views import StoreProductViewSet

app_name = 'products'

router = DefaultRouter() 
router.register('store-product', StoreProductViewSet, basename='store-product')
urlpatterns = router.urls