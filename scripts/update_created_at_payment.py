from sales.models import Payment

def run():
    payments = Payment.objects.all()

    for payment in payments:
        print(payment.sale.created_at)
        print(payment.created_at)

        payment.created_at = payment.sale.created_at
        payment.save()