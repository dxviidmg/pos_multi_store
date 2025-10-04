from rest_framework.routers import DefaultRouter
from . import views
from django.urls import path

app_name = 'logs'



router = DefaultRouter() 
router.register('store-product-log', views.StoreProductLogViewSet, basename='store-product-log')

urlpatterns = router.urls

urlpatterns += [
    path('store-product-log/choices/', views.StoreProductLogsChoicesView.as_view(), name='store-product-logs-choices'),
    path('store-product-logs/', views.StoreProductLogsView.as_view(), name='store-product-logs'),
]