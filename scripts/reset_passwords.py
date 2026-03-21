"""
Resetea contraseñas de usuarios de un tenant y elimina sus tokens de autenticación.
Uso: python manage.py runscript reset_passwords
"""
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


def run():
    users = User.objects.filter(username__icontains='pdbj.')

    for user in users:
        username_list = user.username.split('.')

        if len(username_list) == 3:
            new_password = username_list[2] + "0825"
            print('User', user.username, 'Password', new_password)

            Token.objects.filter(user=user).delete()
#            print(t)

#        username = user.username.replace('admin.', '')
#        user.username = username
            user.set_password(new_password)
            user.save()