from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from tenants.tasks import alert_tenants_without_payment

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

    def test_subscription_status_active_by_default(self):
        t = self._tenant("acc6")
        self.assertEqual(t.subscription_status(), "active")

    def test_subscription_status_cancelled_when_owner_cancels(self):
        t = self._tenant("acc7")
        t.cancelled_at = timezone.now()
        t.save(update_fields=["cancelled_at"])
        self.assertEqual(t.subscription_status(), "cancelled")

    def test_subscription_status_expired_when_mp_cancelled_without_voluntary(self):
        t = self._tenant("acc8")
        # MP dejó la suscripción en cancelled/paused pero el owner NO canceló.
        Subscription.objects.create(
            tenant=t, mp_subscription_id="mp-exp", payer_email="a@b.com",
            status="cancelled",
        )
        self.assertIsNone(t.cancelled_at)
        self.assertEqual(t.subscription_status(), "expired")

    def test_current_card_none_without_data(self):
        t = self._tenant("acc9")
        self.assertIsNone(t.current_card())

    def test_current_card_returns_masked_data(self):
        t = self._tenant("acc10")
        Subscription.objects.create(
            tenant=t, mp_subscription_id="mp-card", payer_email="a@b.com",
            status="authorized", card_brand="visa", card_last_four="7155",
            card_expiration_month=5, card_expiration_year=2031,
        )
        card = t.current_card()
        self.assertEqual(card["brand"], "visa")
        self.assertEqual(card["last_four"], "7155")
        self.assertEqual(card["expiration"], "05/31")


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


class TenantWithoutPaymentAlertTests(TestCase):
    def _old_tenant(self, short_name, hours_ago=25):
        t = Tenant.objects.create(name=short_name, short_name=short_name)
        # created_at es auto_now_add; forzar una fecha antigua.
        Tenant.objects.filter(pk=t.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_ago)
        )
        return Tenant.objects.get(pk=t.pk)

    def test_alerts_tenant_without_payment(self):
        t = self._old_tenant("noPay1")
        result = alert_tenants_without_payment(hours=24)
        self.assertEqual(result, "alertas enviadas: 1")
        t.refresh_from_db()
        self.assertIsNotNone(t.no_payment_alert_sent_at)

    def test_does_not_alert_twice(self):
        self._old_tenant("noPay2")
        alert_tenants_without_payment(hours=24)
        result = alert_tenants_without_payment(hours=24)
        self.assertEqual(result, "alertas enviadas: 0")

    def test_does_not_alert_with_payment(self):
        t = self._old_tenant("noPay3")
        Payment.objects.create(tenant=t, months=1)
        result = alert_tenants_without_payment(hours=24)
        self.assertEqual(result, "alertas enviadas: 0")

    def test_does_not_alert_recent_tenant(self):
        Tenant.objects.create(name="recent", short_name="recent")  # created ahora
        result = alert_tenants_without_payment(hours=24)
        self.assertEqual(result, "alertas enviadas: 0")
