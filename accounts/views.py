from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)

        store = user.get_store()
        return Response({
            'user_id': user.pk,
            'token': token.key,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.get_full_name(),
            'email': user.email,
            'tenant_name': user.get_tenant().name,
            'tenant_short_name': user.get_tenant().short_name,
            'has_sellers': user.get_tenant().has_sellers,
            'store_id': store.id if store else None,
            'store_name': store.name if store else None,
            'store_type': store.store_type if store else None,
            'store_type_display': store.get_store_type_display() if store else None,
            'store_url_printer': store.get_url_printer() if store else None,
            'role': user.get_role()
        })