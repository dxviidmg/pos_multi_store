from django.shortcuts import render
from django.http import JsonResponse
from celery.result import AsyncResult
from rest_framework.views import APIView
from products.decorators import get_store
from django.utils.decorators import method_decorator
from sales.tasks import get_sales_duplicates_task
from rest_framework.response import Response
from logs.tasks import get_logs_duplicates_or_inconsistens_task, get_store_products_inconsistens_task
from products.models import Store

@method_decorator(get_store(), name="dispatch")
class Audit1AsyncView(APIView):
    def get(self, request):
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        store_id = request.GET.get("store_id", None)
        tenant = self.request.user.get_tenant()

        if store_id:
            store_ids = [store_id]
        else:
            stores = Store.objects.filter(tenant=tenant)
            store_ids = list(stores.values_list("id", flat=True))
        
        task1 = get_sales_duplicates_task.delay(store_ids, start_date, end_date)
        task2 = get_logs_duplicates_or_inconsistens_task.delay(store_ids, start_date, end_date)
        return Response({"task1": task1.id, "task2": task2.id})
    

@method_decorator(get_store(), name="dispatch")
class Audit2AsyncView(APIView):
    def get(self, request):
        store_id = request.GET.get("store_id", None)
        tenant = self.request.user.get_tenant()

        if store_id:
            store_ids = [store_id]
        else:
            stores = Store.objects.filter(tenant=tenant)
            store_ids = list(stores.values_list("id", flat=True))
        
        task3 = get_store_products_inconsistens_task.delay(store_ids)
        return Response({"task3": task3.id})
    
# Create your views here.
class TaskResultView(APIView):
    def get(self, request, task_id):
        result = AsyncResult(task_id)
        
        response_data = {
            "task_id": task_id,
            "status": result.status,
        }
        
        if result.ready():
            if result.successful():
                response_data["result"] = result.result
            else:
                error_info = result.info
                response_data["error"] = {
                    "type": type(error_info).__name__,
                    "message": str(error_info)
                } if error_info else "Unknown error"
        else:
            info = result.info or {}
            response_data["info"] = info
            if "percent" in info:
                response_data["percent"] = info["percent"]
        
        return JsonResponse(response_data)