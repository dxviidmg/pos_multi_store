from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('sales-logs-audit/', views.SalesAndLogsAuditView.as_view(), name='sales-logs-audit'),
    path('stock-audit/', views.StockAuditView.as_view(), name='stock-audit'),
    path('product-audit/', views.ProductAuditView.as_view(), name='product-audit'),
    path('product-audit-activity/', views.ProductAuditActivityView.as_view(), name='product-audit-activity'),
    path('task-result/<str:task_id>/', views.TaskResultView.as_view(), name='task-result'),
    path('notifications/', views.OwnerNotificationsView.as_view(), name='notifications'),
]