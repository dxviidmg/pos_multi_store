from rest_framework.routers import DefaultRouter
from . import views
from django.urls import path

app_name = 'products'

router = DefaultRouter() 
router.register('store', views.StoreViewSet, basename='store')
router.register('brand', views.BrandViewSet, basename='brand')
router.register('product', views.ProductViewSet, basename='product')
router.register('store-product', views.StoreProductViewSet, basename='store-product')

router.register('product-transfer', views.ProductTransferViewSet, basename='product-transfer')
urlpatterns = router.urls

urlpatterns += [
    path('confirm-transfers/', views.ConfirmProductTransfersView.as_view(), name='confirm-transfers'),
    path('confirm-distribution/', views.ConfirmDistributionView.as_view(), name='confirm-distribution'),
    path('add-products/', views.AddProductsView.as_view(), name='add-products'),
]