from rest_framework.routers import DefaultRouter
from django.urls import path
from . import views

app_name = 'tenants'

router = DefaultRouter()
router.register('payment', views.PaymentViewSet, basename='payment')
router.register('tenant', views.TenantViewSet, basename='tenant')

urlpatterns = router.urls

urlpatterns += [
    path('tenant-exists/', views.TenantExistsView.as_view(), name='tenant-exists'),
    path('create-tenant/', views.PublicTenantCreateView.as_view(), name='public-tenant-create'),
    path('plans/', views.PublicPlansView.as_view(), name='public-plans'),
    path('redeploy-render/', views.RenderRedeployView.as_view(), name='redeploy-render'),
    path('tenant-info/', views.TenantInfoView.as_view(), name='tenant-info'),
    path('create-products-on-sale/', views.CreateProductsOnSaleView.as_view(), name='create-products-on-sale'),
    path('current-plan/', views.CurrentPlanView.as_view(), name='current-plan'),
    path('plan-equivalent/', views.PlanEquivalentView.as_view(), name='plan-equivalent'),
    path('subscriptions/create/', views.CreateSubscriptionView.as_view(), name='subscriptions-create'),
    path('webhooks/mp/', views.MPWebhookView.as_view(), name='mp-webhook'),
    path('mercadopago/', views.MercadoPagoPreferenceView.as_view(), name='mercadopago-preference'),
]