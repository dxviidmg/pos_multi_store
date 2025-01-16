from rest_framework.routers import DefaultRouter
from .views import SaleViewSet, DailyEarnings, SalesImportValidation, SalesImport
from django.urls import path


app_name = 'sale'

router = DefaultRouter() 
router.register('sale', SaleViewSet, basename='sale')
urlpatterns = router.urls

urlpatterns += [
    path('daily-earnings/', DailyEarnings.as_view(), name='daily-earnings'),
    path('sales-import-validation/', SalesImportValidation.as_view(), name='sales-import-validation'),
    path('sales-import/', SalesImport.as_view(), name='sales-import'),
]