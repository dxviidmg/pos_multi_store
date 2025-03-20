from datetime import date
from django.db.models import Sum
from collections import defaultdict
from .models import Sale, Payment
from products.models import CashFlow

def calculate_cash_summary(store, date, start_date=None, end_date=None):  
    # Obtener totales de CashFlow agrupados por tipo de transacción

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
        sales = Sale.objects.filter(store=store, created_at__date=date)
    else:
        sales = Sale.objects.filter(store=store, created_at__date__range=[start_date, end_date])
    total_sales = sales.aggregate(total=Sum("total"))["total"] or 0

    # Calcular la ganancia total del día sumando el beneficio de cada venta
    total_profit = sum(sale.get_profit() for sale in sales)

    # Obtener pagos relacionados con esas ventas
    if date:
        related_payments = Payment.objects.filter(
            sale__store=store, sale__created_at__date=date
        )
    else:
        related_payments = Payment.objects.filter(
                    sale__store=store, sale__created_at__date__range=[start_date, end_date]
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
                "name": "Total en pagos",
                "amount": total_received_payments,
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
                "amount": "Si" if total_sales == total_received_payments else "No",
                "sales_data": True,
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
                "amount": total_sales + net_cash_flow,
                "total_data": True,
            },
        ]
    )

    return cash_summary
