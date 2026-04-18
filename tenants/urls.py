from rest_framework.routers import DefaultRouter
from django.urls import path
from . import views

app_name = 'tenants'

router = DefaultRouter()
router.register('payment', views.PaymentViewSet, basename='payment')
router.register('tenant', views.TenantViewSet, basename='tenant')

urlpatterns = router.urls

urlpatterns += [
    path('redeploy-render/', views.RenderRedeployView.as_view(), name='redeploy-render'),
    path('tenant-info/', views.TenantInfoView.as_view(), name='tenant-info'),
    path('create-products-on-sale/', views.CreateProductsOnSaleView.as_view(), name='create-products-on-sale'),
]