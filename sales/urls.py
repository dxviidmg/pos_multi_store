from rest_framework.routers import DefaultRouter
from .views import SaleViewSet, DailyEarnings
from django.urls import path


app_name = 'sale'

router = DefaultRouter() 
router.register('sale', SaleViewSet, basename='sale')
urlpatterns = router.urls

urlpatterns += [
    path('daily-earnings/', DailyEarnings.as_view(), name='daily-earnings'),
]