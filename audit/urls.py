from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('audit1/', views.Audit1AsyncView.as_view(), name='audit1'),
    path('audit2/', views.Audit2AsyncView.as_view(), name='audit2'),
    path('product-audit/', views.ProductAuditView.as_view(), name='product-audit'),
    path('product-audit-activity/', views.ProductAuditActivityView.as_view(), name='product-audit-activity'),
    path('task-result/<str:task_id>/', views.TaskResultView.as_view(), name='task-result'),
]