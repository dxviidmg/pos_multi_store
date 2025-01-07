from django.http import Http404
from .models import Tenant

EXCLUDED_PATHS = ['/admin/', '/static/', '/media/']

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(path) for path in EXCLUDED_PATHS):
            return self.get_response(request)
        
        domain = request.get_host().split('.')[0]
        print(request.get_host())
        print('d', domain)
        try:
            request.tenant = Tenant.objects.get(domain=domain)
        except Tenant.DoesNotExist:
            raise Http404("Tenant no encontrado")

        response = self.get_response(request)
        return response
