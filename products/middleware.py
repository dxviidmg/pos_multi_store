class KeepAliveMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Mantener conexión HTTP viva
#        response['Connection'] = 'keep-alive'
#        response['Keep-Alive'] = 'timeout=60, max=100'
        return response