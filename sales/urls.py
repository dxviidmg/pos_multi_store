from rest_framework.routers import DefaultRouter
from . import views 
from django.urls import path


app_name = 'sale'

router = DefaultRouter() 
router.register('sale', views.SaleViewSet, basename='sale')
urlpatterns = router.urls

urlpatterns += [
    path('cash/summary/', views.CashSummary.as_view(), name='cash-summary'),
    path('sales/import-validation/', views.ImportSalesValidation.as_view(), name='import-sales-validation'),
    path('sales/import/', views.ImportSales.as_view(), name='import-sales'),
    path('sales/cancel/', views.CancelSale.as_view(), name='cancel-sale'),
    path('ticket/print/', views.PrintTicketView.as_view(), name='print-ticket'),
]