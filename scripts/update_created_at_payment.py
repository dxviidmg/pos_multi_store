from sales.models import Payment
from tqdm import tqdm

def run():
    payments = Payment.objects.all()

    for payment in tqdm(payments, desc="Update dates", unit="payments"):
        payment.created_at = payment.sale.created_at
        payment.save()