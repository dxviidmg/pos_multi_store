from .views import CustomAuthToken
from django.urls import path

app_name = 'accounts'


urlpatterns = [
    path('api-token-auth/', CustomAuthToken.as_view(), name='api-token-auth'),
]