from rest_framework.routers import DefaultRouter
from . import views 
from django.urls import path


app_name = 'sale'

router = DefaultRouter() 
router.register('sale', views.SaleViewSet, basename='sale')
urlpatterns = router.urls

urlpatterns += [
    path('cash-summary/', views.CashSummary.as_view(), name='cash-summary'),
    path('import-sales-validation/', views.ImportSalesValidation.as_view(), name='import-sales-validation'),
    path('import-sales/', views.ImportSales.as_view(), name='import-sales'),
    path('cancel-sale/', views.CancelSale.as_view(), name='cancel-sale'),
    path('print/ticket/', views.PrintTicketView.as_view(), name='print-ticket'),
]