from collections import defaultdict

from django.db.models import Q, Sum

from products.models import CashFlow
from .models import Sale, Payment, ProductSale


def calculate_cash_summary(store, date=None, start_date=None, end_date=None):
    # --- Construcción de filtro temporal dinámico ---
    if date:
        date_filter = Q(created_at__date=date)
    else:
        date_filter = Q(created_at__date__range=[start_date, end_date])

    # --- Totales de flujo de caja ---
    cash_flows = (
        CashFlow.objects.filter(date_filter, store=store)
        .values("transaction_type")
        .annotate(total=Sum("amount"))
    )

    transaction_sums = defaultdict(
        int,
        {entry["transaction_type"]: entry["total"] for entry in cash_flows},
    )

    total_income = transaction_sums.get("E", 0)
    total_expenses = transaction_sums.get("S", 0)
    net_cash_flow = total_income - total_expenses

    # --- Ventas ---
    sales_filter = Q(store=store, reservation_in_progress=False)
    sales = Sale.objects.filter(sales_filter & date_filter, is_canceled=False)
    sales_canceled = Sale.objects.filter(sales_filter & date_filter, is_canceled=True)

    total_profit = sum(sale.get_profit() for sale in sales)

    # --- Pagos ---
    related_payments = Payment.objects.filter(
        sale__store=store, sale__is_canceled=False
    ).filter(date_filter)

    payments_grouped = related_payments.values("payment_method").annotate(
        total_amount=Sum("amount")
    )

    total_received = related_payments.aggregate(total=Sum("amount"))["total"] or 0

    # --- Métodos de pago ---
    payment_labels = dict(Payment.PAYMENT_METHOD_CHOICES)
    payments_dict = {method: 0 for method in payment_labels.keys()}

    for p in payments_grouped:
        payments_dict[p["payment_method"]] = p["total_amount"]

    
    # --- Construcción de resultados ---
    cash_summary = [
        {
            "name": payment_labels.get(method, method),
            "amount": amount,
            "payment_method_data": True,
        }
        for method, amount in payments_dict.items()
    ]

    # --- Totales generales ---
    efectivo_amount = next(
        (item["amount"] for item in cash_summary if item["name"] == "Efectivo"), 0
    )
    net_cash = efectivo_amount + net_cash_flow

    # --- Extensión con métricas ---
    cash_summary.extend(
        [
            {
                "name": "Total de ventas",
                "amount": total_received,
                "payment_method_data": True,
                "sales_data": True,
                "total_data": True,
            },
            {"name": "Entradas", "amount": total_income, "cashflow_data": True},
            {
                "name": "Salidas",
                "amount": f"-{total_expenses}" if total_expenses else "0",
                "cashflow_data": True,
            },
            {
                "name": "Total de E/S",
                "amount": net_cash_flow,
                "cashflow_data": True,
                "total_data": True,
            },
            {"name": "Total en caja", "amount": net_cash, "total_data": True},
            {"name": "Total de ganancias", "amount": total_profit},
            {
                "name": "Total",
                "amount": total_received + net_cash_flow,
                "total_data": True,
            },
            {"name": "Número de ventas", "amount": sales.count()},
            {
                "name": "Ventas canceladas",
                "amount": sales_canceled.count(),
                "total_data": True,
            },
            {
                "name": "Distribuciones pendientes",
                "amount": store.count_pending_distributions(),
                "total_data": True,
            },
            {
                "name": "Traspasos pendientes",
                "amount": store.count_pending_transfers(),
                "total_data": True,
            },
        ]
    )

    return cash_summary


def calculate_cash_summary_by_department(
    store, date=None, start_date=None, end_date=None, department_id=None
):
    # --- Normalizar parámetros ---
    if department_id == "0":
        department_id = None

    # --- Filtros de fecha ---
    date_filter = Q(sale__store=store, sale__is_canceled=False)
    date_filter2 = Q()

    if date:
        date_filter &= Q(created_at__date=date)
        date_filter2 = Q(created_at__date=date)
    else:
        date_filter &= Q(created_at__date__range=[start_date, end_date])
        date_filter2 = Q(created_at__date__range=[start_date, end_date])

    # --- Pagos relacionados ---
    related_payments = Payment.objects.filter(date_filter)
    sales_ids = related_payments.values_list("sale_id", flat=True).distinct()

    # --- Productos vendidos ---
    product_filter = Q(sale_id__in=sales_ids)
    if department_id:
        product_filter &= Q(product__department=department_id)

    products_sale = ProductSale.objects.filter(product_filter)

    # --- Agregaciones SQL si los campos existen ---
    totals = products_sale.aggregate(total_received=Sum("price", default=0))
    total_received = totals.get("total_received") or 0

    # --- Ganancia total (usa método Python si no es campo en BD) ---
    try:
        # Si el modelo no tiene un campo "profit", usa método
        total_profit = sum(p.get_profit() for p in products_sale)
    except Exception:
        total_profit = 0

    # --- Ventas únicas y canceladas ---
    sale_count = products_sale.values("sale_id").distinct().count()

    sales_canceled_count = Sale.objects.filter(
        date_filter2, store=store, reservation_in_progress=False, is_canceled=True
    ).count()

    # --- Métodos de pago ---
    payment_method_labels = dict(Payment.PAYMENT_METHOD_CHOICES)

    # Agrupar montos reales por método
    payments_summary = (
        related_payments.values("payment_method")
        .annotate(total=Sum("amount"))
        .values_list("payment_method", "total")
    )

    # Inicializar diccionario con todos los métodos
    payments_dict = {method: 0 for method in payment_method_labels}
    for method, total in payments_summary:
        payments_dict[method] = total or 0

    # --- Construcción del resumen ---
    cash_summary = [
        {
            "name": payment_method_labels[method],
            "amount": amount,
            "payment_method_data": True,
        }
        for method, amount in payments_dict.items()
    ]

    # --- Secciones adicionales ---
    cash_summary.extend(
        [
            {
                "name": "Total en pagos",
                "amount": total_received,
                "payment_method_data": True,
                "sales_data": True,
            },
            {"name": "Entradas", "amount": 0, "cashflow_data": True},
            {"name": "Salidas", "amount": 0, "cashflow_data": True},
            {
                "name": "Total de E/S",
                "amount": 0,
                "cashflow_data": True,
                "total_data": True,
            },
            {"name": "Total en caja", "amount": 0, "total_data": True},
            {"name": "Total de ganancias", "amount": total_profit},
            {"name": "Total", "amount": 0, "total_data": True},
            {"name": "Numero de ventas", "amount": sale_count},
            {
                "name": "Ventas canceladas",
                "amount": sales_canceled_count,
                "total_data": True,
            },
        ]
    )

    return cash_summary


def calculate_total_sales_by_seller(seller, start_date, end_date):

    sales = Sale.objects.filter(
        seller=seller,
        created_at__date__range=[start_date, end_date],
        reservation_in_progress=False,
        is_canceled=False,
    )
    total_sales = sales.aggregate(total=Sum("total"))["total"] or 0
    return total_sales
