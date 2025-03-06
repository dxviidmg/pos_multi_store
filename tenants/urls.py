from rest_framework.routers import DefaultRouter
from . import views 
from django.urls import path


app_name = 'tenants'

router = DefaultRouter() 
router.register('payment', views.PaymentViewSet, basename='payment')
urlpatterns = router.urls

urlpatterns += [
    path('tenant-notices/', views.TenantNoticesView.as_view(), name='tenant-notices'),
]