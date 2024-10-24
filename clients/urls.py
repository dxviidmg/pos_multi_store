from rest_framework.routers import DefaultRouter
from .views import ClientViewSet

app_name = 'clients'

router = DefaultRouter() 
router.register('client', ClientViewSet, basename='client')
urlpatterns = router.urls