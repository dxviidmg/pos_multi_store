from django.contrib.auth.models import User

def run():
    users = User.objects.filter(username__icontains='admin.')

    for user in users:
        username = user.username.replace('admin.', '')
        user.username = username
        user.set_password(username)
        user.save()