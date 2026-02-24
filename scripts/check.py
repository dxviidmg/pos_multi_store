from sales.models import Sale

def run():
    sales = Sale.objects.filter(created_at__year=2026, created_at__month=1, created_at__day=23, created_at__hour=12, created_at__minute=50)
    print(sales)
    print(len(sales))
