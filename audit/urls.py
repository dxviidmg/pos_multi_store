from . import views
from django.urls import path

app_name = 'audit'
urlpatterns = [
    path('audit1/', views.Audit1AsyncView.as_view(), name='audit1'),
    path('audit2/', views.Audit2AsyncView.as_view(), name='audit2'),
    path('task-result/<str:task_id>/', views.TaskResultView.as_view(), name='task-result'),
]