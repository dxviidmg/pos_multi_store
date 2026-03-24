from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.decorators import action
from django.contrib.auth.models import User
from .serializers import UserSerializer
from products.models import Store


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        user_id = request.data.get('user_id')
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not old_password or not new_password or not confirm_password:
            return Response({'error': 'Todos los campos son requeridos'}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({'error': 'Las contraseñas no coinciden'}, status=status.HTTP_400_BAD_REQUEST)
        
        if user_id:
            user_id = int(user_id)
            if request.user.id != user_id:
                # Validar si el request.user es owner
                from tenants.models import Tenant
                from products.models import Store
                tenant = Tenant.objects.filter(owner=request.user).first()
                if tenant:
                    # Validar que user_id sea manager de una tienda del owner
                    if not Store.objects.filter(tenant=tenant, manager_id=user_id).exists():
                        return Response({'error': 'No puedes cambiar la contraseña de otro usuario'}, status=status.HTTP_403_FORBIDDEN)
                    # Owner cambia contraseña de manager, validar contraseña del owner
                    if not request.user.check_password(old_password):
                        return Response({'error': 'Contraseña actual incorrecta'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({'error': 'No puedes cambiar la contraseña de otro usuario'}, status=status.HTTP_403_FORBIDDEN)
            else:
                # Usuario cambia su propia contraseña
                if not request.user.check_password(old_password):
                    return Response({'error': 'Contraseña actual incorrecta'}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.get(id=user_id)
        else:
            # Usuario cambia su propia contraseña
            if not request.user.check_password(old_password):
                return Response({'error': 'Contraseña actual incorrecta'}, status=status.HTTP_400_BAD_REQUEST)
            user = request.user

        user.set_password(new_password)
        user.save()
        return Response({'message': 'Contraseña actualizada exitosamente'})


class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)

        from tenants.models import Tenant
        from products.models import Store, StoreWorker

        tenant = Tenant.objects.filter(owner=user).first()
        if tenant:
            role = 'owner'
            store = None
        else:
            store = Store.objects.filter(manager=user).select_related('tenant').first()
            if store:
                role = 'manager'
                tenant = store.tenant
            else:
                sw = StoreWorker.objects.filter(worker=user).select_related('store__tenant').first()
                role = 'seller' if sw else 'Sin definir'
                store = sw.store if sw else None
                tenant = store.tenant if store else None

        data = {
            'user_id': user.pk,
            'token': token.key,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.get_full_name(),
            'email': user.email,
            'tenant_id': tenant.id if tenant else None,
            'tenant_name': tenant.name if tenant else None,
            'tenant_short_name': tenant.short_name if tenant else None,
            'store_id': store.id if store else None,
            'store_name': store.name if store else None,
            'store_type': store.store_type if store else None,
            'store_type_display': store.get_store_type_display() if store else None,
            'store_printer': store.get_store_printer() if store else None,
            'role': role,
        }
        if role == 'owner':
            data['store_count'] = Store.objects.filter(tenant=tenant).count()
        return Response(data)