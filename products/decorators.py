from products.models import Store

def get_store():
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            store_id = request.headers.get("store-id")
            if store_id:
                store = Store.objects.get(id=store_id)
            else:
                store = None
            request.store = store
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator