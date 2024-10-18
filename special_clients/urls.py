from rest_framework.routers import DefaultRouter
from .views import SpecialClientViewSet

app_name = 'special_clients'

router = DefaultRouter() 
router.register('special-client', SpecialClientViewSet, basename='special-clients')
urlpatterns = router.urls