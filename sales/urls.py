from rest_framework.routers import DefaultRouter
from django.urls import path
from . import views

app_name = 'sales'

router = DefaultRouter()
router.register('sale', views.SaleViewSet, basename='sale')

urlpatterns = router.urls

urlpatterns += [
    path('cash/summary/', views.CashSummaryView.as_view(), name='cash-summary'),
    path('sales/cancel/', views.SaleCancelView.as_view(), name='sale-cancel'),
    path('sales/import/', views.SaleImportView.as_view(), name='sale-import'),
    path('sales/import-validation/', views.SaleImportValidationView.as_view(), name='sale-import-validation'),
    path('sales-dashboard/', views.SaleDashboardAsyncView.as_view(), name='sales-dashboard'),
]