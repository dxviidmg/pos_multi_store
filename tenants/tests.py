from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from tenants.models import Plan, Tenant, Payment, Subscription


class TenantAccessTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(
            name="Test", price=500, stores=1, billing_type="S"
        )

    def _tenant(self, short_name):
        # Tenant.save() crea el owner automáticamente.
        return Tenant.objects.create(name=short_name, short_name=short_name, plan=self.plan)

    def test_has_access_without_payment_is_true_provisional(self):
        t = self._tenant("acc1")
        # Decisión provisional (b): sin Payment -> acceso concedido.
        self.assertTrue(t.has_access())
        self.assertIsNone(t.access_until())

    def test_has_access_with_valid_payment(self):
        t = self._tenant("acc2")
        p = Payment(tenant=t, months=1)
        p.save()
        # end_of_validity queda en el futuro (mes vigente).
        p.end_of_validity = timezone.localdate() + timedelta(days=5)
        p.save(update_fields=["end_of_validity"])
        self.assertTrue(t.has_access())
        self.assertEqual(t.access_until(), timezone.localdate() + timedelta(days=5))

    def test_no_access_when_expired(self):
        t = self._tenant("acc3")
        p = Payment(tenant=t, months=1)
        p.save()
        p.end_of_validity = timezone.localdate() - timedelta(days=1)
        p.save(update_fields=["end_of_validity"])
        self.assertFalse(t.has_access())

    def test_access_on_exact_expiry_day_inclusive(self):
        t = self._tenant("acc4")
        p = Payment(tenant=t, months=1)
        p.save()
        p.end_of_validity = timezone.localdate()  # vence hoy
        p.save(update_fields=["end_of_validity"])
        self.assertTrue(t.has_access())  # inclusive

    def test_is_cancelled_derived_from_cancelled_at(self):
        t = self._tenant("acc5")
        self.assertFalse(t.is_cancelled)
        t.cancelled_at = timezone.now()
        t.save(update_fields=["cancelled_at"])
        self.assertTrue(t.is_cancelled)


class SubscriptionStatusTests(TestCase):
    def test_default_status_is_authorized(self):
        plan = Plan.objects.create(name="P", price=500, stores=1, billing_type="S")
        t = Tenant.objects.create(name="s1", short_name="s1", plan=plan)
        sub = Subscription.objects.create(
            tenant=t, mp_subscription_id="mp-1", payer_email="a@b.com"
        )
        self.assertEqual(sub.status, "authorized")

    def test_status_choices_aligned_with_mp(self):
        values = {c[0] for c in Subscription.STATUS_CHOICES}
        self.assertEqual(values, {"pending", "authorized", "paused", "cancelled"})
