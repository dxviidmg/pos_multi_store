from rest_framework.routers import DefaultRouter
from django.urls import path
from . import views

app_name = 'logs'

router = DefaultRouter()
router.register('store-product-log', views.StoreProductLogViewSet, basename='store-product-log')

urlpatterns = router.urls

urlpatterns += [
    path('store-product-logs/', views.StoreProductLogsView.as_view(), name='store-product-logs'),
    path('store-product-logs/choices/', views.StoreProductLogsChoicesView.as_view(), name='store-product-logs-choices'),
]