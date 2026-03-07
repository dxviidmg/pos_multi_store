from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('api-token-auth/', views.CustomAuthToken.as_view(), name='api-token-auth'),
]