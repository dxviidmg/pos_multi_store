from rest_framework.routers import DefaultRouter
from .views import SaleViewSet

app_name = 'sale'

router = DefaultRouter() 
router.register('sale', SaleViewSet, basename='sale')
urlpatterns = router.urls