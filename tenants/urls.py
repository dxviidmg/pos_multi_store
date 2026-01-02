from rest_framework.routers import DefaultRouter
from . import views 
from django.urls import path


app_name = 'tenants'

router = DefaultRouter() 
router.register('payment', views.PaymentViewSet, basename='payment')
urlpatterns = router.urls

urlpatterns += [
    path('tenant-info/', views.TenantInfoView.as_view(), name='tenant-info'),
    path('redeploy-render/', views.RenderRedeployView.as_view(), name='redeploy-render'),
]