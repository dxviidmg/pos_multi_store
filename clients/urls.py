from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, DiscountViewSet

app_name = 'clients'

router = DefaultRouter() 
router.register('client', ClientViewSet, basename='client')
router.register('discount', DiscountViewSet, basename='discount')

urlpatterns = router.urls

