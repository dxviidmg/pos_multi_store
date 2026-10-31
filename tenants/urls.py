from rest_framework.routers import DefaultRouter
from django.urls import path
from . import views

app_name = 'tenants'

router = DefaultRouter()
router.register('payment', views.PaymentViewSet, basename='payment')
router.register('tenant', views.TenantViewSet, basename='tenant')

urlpatterns = router.urls

urlpatterns += [
    path('tenants/', views.AdminTenantListView.as_view(), name='admin-tenant-list'),
    path('tenants/create/', views.AdminTenantCreateView.as_view(), name='admin-tenant-create'),
    path('admin-plans/', views.AdminPlansView.as_view(), name='admin-plans'),
    path('admin-tenant-exists/', views.AdminTenantExistsView.as_view(), name='admin-tenant-exists'),
    path('payments-total/', views.AdminPaymentsTotalView.as_view(), name='admin-payments-total'),
    path('payments-by-tenant/', views.AdminPaymentsByTenantView.as_view(), name='admin-payments-by-tenant'),
    path('payments/create/', views.AdminPaymentCreateView.as_view(), name='admin-payment-create'),
    path('tenant-exists/', views.TenantExistsView.as_view(), name='tenant-exists'),
    path('stores-count/', views.StoresCountView.as_view(), name='stores-count'),
    path('tenants/register/', views.PublicTenantCreateView.as_view(), name='public-tenant-create'),
    # Alias deprecado: mantener hasta migrar el frontend a tenants/register/
    path('create-tenant/', views.PublicTenantCreateView.as_view(), name='public-tenant-create-legacy'),
    path('plans/', views.PublicPlansView.as_view(), name='public-plans'),
    path('redeploy-render/', views.RenderRedeployView.as_view(), name='redeploy-render'),
    path('tenant-info/', views.TenantInfoView.as_view(), name='tenant-info'),
    path('create-products-on-sale/', views.CreateProductsOnSaleView.as_view(), name='create-products-on-sale'),
    path('can-create-store/', views.CanCreateStoreView.as_view(), name='can-create-store'),
    path('current-plan/', views.CurrentPlanView.as_view(), name='current-plan'),
    path('plan-equivalent/', views.PlanEquivalentView.as_view(), name='plan-equivalent'),
    path('subscriptions/create/', views.CreateSubscriptionView.as_view(), name='subscriptions-create'),
    path('subscriptions/cancel/', views.SubscriptionCancelView.as_view(), name='subscriptions-cancel'),
    path('subscriptions/update-card/', views.SubscriptionUpdateCardView.as_view(), name='subscriptions-update-card'),
    path('subscriptions/', views.SubscriptionView.as_view(), name='subscription-detail'),
    path('tenant-dates/', views.TenantDatesView.as_view(), name='tenant-dates'),
    path('webhooks/mp/', views.MPWebhookView.as_view(), name='mp-webhook'),
    path('mercadopago/', views.MercadoPagoPreferenceView.as_view(), name='mercadopago-preference'),
]