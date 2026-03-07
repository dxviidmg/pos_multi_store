from rest_framework.routers import DefaultRouter
from . import views 
from django.urls import path


app_name = 'sale'

router = DefaultRouter() 
router.register('sale', views.SaleViewSet, basename='sale')
urlpatterns = router.urls

urlpatterns += [
    path('cash/summary/', views.CashSummaryView.as_view(), name='cash-summary'),
    path('sales/import-validation/', views.SaleImportValidationView.as_view(), name='import-sales-validation'),
    path('sales/import/', views.SaleImportView.as_view(), name='import-sales'),
    path('sales/cancel/', views.SaleCancelView.as_view(), name='cancel-sale'),
    path('sales-dashboard/', views.SaleDashboardAsyncView.as_view(), name='sales-dashboard'),
]