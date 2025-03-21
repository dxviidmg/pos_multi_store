from rest_framework.routers import DefaultRouter
from . import views
from django.urls import path

app_name = 'products'

router = DefaultRouter() 
router.register('store', views.StoreViewSet, basename='store')
router.register('brand', views.BrandViewSet, basename='brand')
router.register('product', views.ProductViewSet, basename='product')
router.register('store-product', views.StoreProductViewSet, basename='store-product')
router.register('transfer', views.TransferViewSet, basename='transfer')
router.register('cash-flow', views.CashFlowViewSet, basename='cash-flow')
router.register('store-worker', views.StoreWorkerViewSet, basename='store-worker')

urlpatterns = router.urls

urlpatterns += [
    path('transfers/confirm/', views.ConfirmProductTransfersView.as_view(), name='transfers-confirm'),
    path('store-product/distribution/confirm/', views.ConfirmDistributionView.as_view(), name='confirm-distribution'),
    path('store-product-logs/', views.StoreProductLogsView.as_view(), name='store-product-logs'),
    path('store-product-logs/choices/', views.StoreProductLogsChoicesView.as_view(), name='store-product-logs-choices'),
    path('store/investment/<int:pk>/', views.StoreInvestmentView.as_view(), name='store-investment'),
    path('investments/', views.InvestmentsView.as_view(), name='investments'),
    path('products/add/', views.AddProductsView.as_view(), name='add-products'),
    path('products/import-validation/', views.ProductImportValidation.as_view(), name='product-import-validation'),
    path('products/import/', views.ProductImport.as_view(), name='product-import'),
    path('products/delete/', views.DeleteProductsView.as_view(), name='products-delete'),
    path('brands/delete/', views.DeleteBrandsView.as_view(), name='brands-delete'),
]