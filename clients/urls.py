from rest_framework.routers import DefaultRouter
from . import views

app_name = 'clients'

router = DefaultRouter()
router.register('client', views.ClientViewSet, basename='client')
router.register('discount', views.DiscountViewSet, basename='discount')

urlpatterns = router.urls

