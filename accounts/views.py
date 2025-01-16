from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'user_id': user.pk,
            'token': token.key,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.get_full_name(),
            'email': user.email,
            'tenant_name': user.get_tenant().name,
            'store_name': user.get_store().get_full_name() if user.get_store() else None,
            'store_type': user.get_store().store_type if user.get_store() else None
            })