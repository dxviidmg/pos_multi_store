from rest_framework.routers import DefaultRouter
from . import views
from django.urls import path

app_name = 'logs'

urlpatterns = [
    path('store-product-log/', views.StoreProductLogsView.as_view(), name='store-product-logs'),
    path('store-product-log/choices/', views.StoreProductLogsChoicesView.as_view(), name='store-product-logs-choices'),
]