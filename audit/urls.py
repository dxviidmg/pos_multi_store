from . import views
from django.urls import path

app_name = 'audit'
urlpatterns = [
    path('get-audit/', views.SaleAsyncView.as_view(), name='async-sale'),
    path('task-result/<str:task_id>/', views.TaskResultView.as_view(), name='task-result'),
]