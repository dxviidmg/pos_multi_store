from django.shortcuts import render
from django.http import JsonResponse
from celery.result import AsyncResult
from rest_framework.views import APIView
from products.decorators import get_store
from django.utils.decorators import method_decorator
from sales.tasks import get_sales_duplicates_task
from rest_framework.response import Response
from logs.tasks import get_logs_duplicates_or_inconsistens_task, get_store_products_inconsistens_task

@method_decorator(get_store(), name="dispatch")
class SaleAsyncView(APIView):
    def get(self, request):
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        store = request.store
        tenant = self.request.user.get_tenant()
        print(tenant)

        task1 = get_sales_duplicates_task.delay(tenant.id, start_date, end_date)
        task2 = get_logs_duplicates_or_inconsistens_task.delay(tenant.id, start_date, end_date)
        task3 = get_store_products_inconsistens_task.delay(tenant.id)
        return Response({"task1": task1.id, "task2": task2.id, "task3": task3.id})
    

# Create your views here.
class TaskResultView(APIView):
    def get(self, request, task_id):
        result = AsyncResult(task_id)
        return JsonResponse(
            {
                "task_id": task_id,
                "status": result.status,
                "result": result.result if result.ready() else None,
                "info": result.info if result.info else {}
            }
        )