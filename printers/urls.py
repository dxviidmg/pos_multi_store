from rest_framework.routers import DefaultRouter
from . import views

app_name = 'printers'

router = DefaultRouter()
router.register('store-printer', views.StorePrinterViewSet, basename='store-printer')

urlpatterns = router.urls