from rest_framework.routers import DefaultRouter
from django.urls import path
from . import views

app_name = 'products'

router = DefaultRouter()
router.register('store', views.StoreViewSet, basename='store')
router.register('brand', views.BrandViewSet, basename='brand')
router.register('department', views.DepartmentViewSet, basename='department')
router.register('product', views.ProductViewSet, basename='product')
router.register('store-product', views.StoreProductViewSet, basename='store-product')
router.register('transfer', views.TransferViewSet, basename='transfer')
router.register('cash-flow', views.CashFlowViewSet, basename='cash-flow')
router.register('store-worker', views.StoreWorkerViewSet, basename='store-worker')
router.register('stock-update-request', views.StockUpdateRequestViewSet, basename='stock-update-request')
router.register('distribution', views.DistributionViewSet, basename='distribution')

urlpatterns = router.urls

urlpatterns += [
    path('store/<int:pk>/investment/', views.StoreInvestmentView.as_view(), name='store-investment'),
    path('store/<int:pk>/reset-stock/', views.ResetStoreStockView.as_view(), name='store-reset-stock'),
    path('brands/delete/', views.BrandDeleteView.as_view(), name='brands-delete'),
    path('departments/delete/', views.DepartmentDeleteView.as_view(), name='departments-delete'),
    path('products/add/', views.ProductAddView.as_view(), name='product-add'),
    path('products/delete/', views.ProductDeleteView.as_view(), name='products-delete'),
    path('products/import/', views.ProductImport.as_view(), name='product-import'),
    path('products/import-validation/', views.ProductImportValidationView.as_view(), name='product-import-validation'),
    path('products/reassign/', views.ProductReassignView.as_view(), name='product-reassign'),
    path('products/stock-other-stores/', views.StockInOtherStores.as_view(), name='product-stock-other-stores'),
    path('products/upper-code/', views.ProductUpperCodeView.as_view(), name='product-upper-code'),
    path('store-product/distribution/confirm/', views.ConfirmDistributionView.as_view(), name='store-product-distribution-confirm'),
    path('store-products/import/', views.ImportStoreProductView.as_view(), name='store-product-import'),
    path('store-products/import-validation/', views.StoreProductImportValidationView.as_view(), name='store-product-import-validation'),
    path('store-products/import/can-include-quantity/', views.StoreProductCanIncludeQuantityView.as_view(), name='store-product-can-include-quantity'),
    path('transfers/confirm/', views.TransferConfirmView.as_view(), name='transfers-confirm'),
    path('ping/', views.ping, name='ping'),
]