from datetime import date
from django.db.models import Sum
from collections import defaultdict
from .models import Sale, Payment, ProductSale
from products.models import CashFlow

def calculate_cash_summary(store, date, start_date=None, end_date=None):  
    if date:
        cash_flow_totals_by_type = (
            CashFlow.objects.filter(store=store, created_at__date=date)
            .values("transaction_type")
            .annotate(total=Sum("amount"))
        )
    else:

        cash_flow_totals_by_type = (
            CashFlow.objects.filter(store=store, created_at__date__range=[start_date, end_date])
            .values("transaction_type")
            .annotate(total=Sum("amount"))
        )
    # Mapear los totales en un defaultdict para evitar valores None
    transaction_sums = defaultdict(
        int,
        {entry["transaction_type"]: entry["total"] for entry in cash_flow_totals_by_type},
    )
    total_income = transaction_sums["E"]
    total_expenses = transaction_sums["S"]
    net_cash_flow = total_income - total_expenses

    # Obtener total de ventas
    if date:
        sales = Sale.objects.filter(store=store, created_at__date=date, reservation_in_progress=False)
    else:
        sales = Sale.objects.filter(store=store, created_at__date__range=[start_date, end_date], reservation_in_progress=False)
    total_sales = sales.aggregate(total=Sum("total"))["total"] or 0

    # Calcular la ganancia total del día sumando el beneficio de cada venta
    total_profit = sum(sale.get_profit() for sale in sales)

    # Obtener pagos relacionados con esas ventas
    if date:
        related_payments = Payment.objects.filter(
            sale__store=store, created_at__date=date
        )

    else:
        related_payments = Payment.objects.filter(
                    sale__store=store, created_at__date__range=[start_date, end_date]
                )        
    payments_grouped_by_method = related_payments.values("payment_method").annotate(
        total_amount=Sum("amount")
    )
    total_received_payments = (
        related_payments.aggregate(total=Sum("amount"))["total"] or 0
    )

        # Mapeo de métodos de pago
    payment_method_labels = dict(Payment.PAYMENT_METHOD_CHOICES)

    # Crear un diccionario con todos los métodos de pago y valores iniciales en 0
    payments_dict = {method: 0 for method in payment_method_labels.keys()}

    # Actualizar con los valores reales obtenidos de la base de datos
    for payment in payments_grouped_by_method:
        payments_dict[payment["payment_method"]] = payment["total_amount"]

    # Construcción de la respuesta, asegurando que todos los métodos estén presentes
    cash_summary = [
        {
            "name": payment_method_labels.get(method, method),
            "amount": amount,
            "payment_method_data": True,
        }
        for method, amount in payments_dict.items()
    ]


    net_cash = (
        next(
            (item for item in cash_summary if item["name"] == "Efectivo"),
            {"amount": 0},
        )["amount"]
        + net_cash_flow
    )

    cash_summary.extend(
        [
            {
                "name": "Total de ventas",
                "amount": total_received_payments,
                "payment_method_data": True,
                "sales_data": True,
                "total_data": True,
            },
            {"name": "Entradas", "amount": total_income, "cashflow_data": True},
            {
                "name": "Salidas",
                "amount": f"-{total_expenses}" if total_expenses != 0 else str(total_expenses),
                "cashflow_data": True,
            },
            {
                "name": "Total de E/S",
                "amount": net_cash_flow,
                "cashflow_data": True,
                "total_data": True,
            },
            {
                "name": "Total en caja",
                "amount": net_cash,
                "total_data": True,
            },
            {
                "name": "Total de ganancias",
                "amount": total_profit,
            },
            {
                "name": "Total",
                "amount": total_received_payments + net_cash_flow,
                "total_data": True,
            },
            {
                "name": "Numero de ventas",
                "amount": sales.count(),
            },
        ]
    )
    return cash_summary


def calculate_cash_summary_by_department(store, date, start_date=None, end_date=None, department_id=""):  
    if date:
        sales = Sale.objects.filter(store=store, created_at__date=date, reservation_in_progress=False)
    else:
        sales = Sale.objects.filter(store=store, created_at__date__range=[start_date, end_date], reservation_in_progress=False)
    
    if department_id == "0":
        department_id = None

    products_sale = ProductSale.objects.filter(sale__in=sales, product__department=department_id, reservation_in_progress=False)
    total_sales = sum(product_sale.get_total() for product_sale in products_sale)
    total_profit = sum(product_sale.get_profit() for product_sale in products_sale)

    sale_count = products_sale.values_list('sale_id').distinct().count()
    payment_method_labels = dict(Payment.PAYMENT_METHOD_CHOICES)

    # Crear un diccionario con todos los métodos de pago y valores iniciales en 0
    payments_dict = {method: 0 for method in payment_method_labels.keys()}
    cash_summary = [
        {
            "name": payment_method_labels.get(method, method),
            "amount": amount,
            "payment_method_data": True,
        }
        for method, amount in payments_dict.items()
    ]

    cash_summary.extend(
        [
            {
                "name": "Total en pagos",
                "amount": 0,
                "payment_method_data": True,
                "sales_data": True,
            },
            {
                "name": "Total en ventas",
                "amount": total_sales,
                "sales_data": True,
                "total_data": True,
            },

            {
                "name": "Balanceado",
                "amount": 0,
                "sales_data": True,
            },
            {"name": "Entradas", "amount": 0, "cashflow_data": True},
            {
                "name": "Salidas",
                "amount": 0,
                "cashflow_data": True,
            },
            {
                "name": "Total de E/S",
                "amount": 0,
                "cashflow_data": True,
                "total_data": True,
            },
            {
                "name": "Total en caja",
                "amount": 0,
                "total_data": True,
            },
            {
                "name": "Total de ganancias",
                "amount": 0,
                "amount": total_profit,
            },
            {
                "name": "Total",
                "amount": 0,
                "total_data": True,
            },
                        {
                "name": "Numero de ventas",
                "amount": sale_count,
            },
        ]
    )

    return cash_summary


def calculate_total_sales_by_seller(seller, start_date, end_date):  

    sales = Sale.objects.filter(seller=seller, created_at__date__range=[start_date, end_date], reservation_in_progress=False)
    total_sales = sales.aggregate(total=Sum("total"))["total"] or 0
    return total_sales