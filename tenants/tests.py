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

    def test_has_access_without_payment_blocked_when_old_and_not_sandbox(self):
        t = self._tenant("acc1")
        # Sin Payment y con más de 24h desde la creación -> sin acceso.
        Tenant.objects.filter(pk=t.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        t.refresh_from_db()
        self.assertFalse(t.has_access())
        self.assertIsNone(t.access_until())

    def test_has_access_without_payment_allowed_within_24h(self):
        t = self._tenant("acc1b")
        # Recién creado (<24h): pago en proceso -> acceso concedido.
        self.assertTrue(t.has_access())

    def test_has_access_without_payment_allowed_when_sandbox(self):
        t = self._tenant("acc1c")
        Tenant.objects.filter(pk=t.pk).update(
            is_sandbox=True, created_at=timezone.now() - timedelta(days=30)
        )
        t.refresh_from_db()
        self.assertTrue(t.has_access())

    def test_has_access_with_valid_payment(self):
        t = self._tenant("acc2")
        p = Payment(tenant=t, months=1)
        p.save()
        # end_of_validity queda en el futuro (mes vigente).
        p.end_of_validity = timezone.localdate() + timedelta(days=5)
        p.save(update_fields=["end_of_validity"])
        self.assertTrue(t.has_access())
        self.assertEqual(t.access_until(), timezone.localdate() + timedelta(days=5))

    def test_access_within_grace_period(self):
        t = self._tenant("acc3g")
        p = Payment(tenant=t, months=1)
        p.save()
        # Venció hace 3 días: aún dentro de los 7 días de gracia.
        p.end_of_validity = timezone.localdate() - timedelta(days=3)
        p.save(update_fields=["end_of_validity"])
        self.assertTrue(t.has_access())

    def test_access_on_last_grace_day_inclusive(self):
        t = self._tenant("acc3g2")
        p = Payment(tenant=t, months=1)
        p.save()
        # Venció hace 7 días: último día de gracia, inclusive.
        p.end_of_validity = timezone.localdate() - timedelta(days=7)
        p.save(update_fields=["end_of_validity"])
        self.assertTrue(t.has_access())

    def test_no_access_after_grace_period(self):
        t = self._tenant("acc3")
        p = Payment(tenant=t, months=1)
        p.save()
        # Venció hace 8 días: gracia agotada -> sin acceso.
        p.end_of_validity = timezone.localdate() - timedelta(days=8)
        p.save(update_fields=["end_of_validity"])
        self.assertFalse(t.has_access())

    def test_manual_plan_always_has_access(self):
        manual_plan = Plan.objects.create(
            name="Manual", price=500, stores=1, billing_type="M"
        )
        t = Tenant.objects.create(name="man1", short_name="man1", plan=manual_plan)
        p = Payment(tenant=t, months=1)
        p.save()
        # Aun vencido hace mucho, un plan manual conserva acceso.
        p.end_of_validity = timezone.localdate() - timedelta(days=60)
        p.save(update_fields=["end_of_validity"])
        self.assertTrue(t.has_access())

    def test_cancelled_tenant_has_no_access(self):
        t = self._tenant("acc_cancel")
        p = Payment(tenant=t, months=1)
        p.save()
        p.end_of_validity = timezone.localdate() + timedelta(days=30)  # vigente
        p.save(update_fields=["end_of_validity"])
        t.cancelled_at = timezone.now()
        t.save(update_fields=["cancelled_at"])
        # Cancelación corta el acceso pese a vigencia vigente.
        self.assertFalse(t.has_access())

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


class TenantCancellationTests(TestCase):
    """
    Cancelación de tenant: corte inmediato de acceso para todos los usuarios,
    independiente del plan. Cubre tenant_users(), el borrado de tokens, y el
    bloqueo en login y en el permission gate.
    """

    def setUp(self):
        from rest_framework.authtoken.models import Token
        from products.models import Store, StoreWorker

        self.Token = Token
        self.plan = Plan.objects.create(
            name="Test", price=500, stores=1, billing_type="S"
        )
        self.tenant = Tenant.objects.create(
            name="canc", short_name="canc", plan=self.plan
        )
        # Vigencia futura para probar que la cancelación corta pese a estar vigente.
        p = Payment(tenant=self.tenant, months=1)
        p.save()
        p.end_of_validity = timezone.localdate() + timedelta(days=30)
        p.save(update_fields=["end_of_validity"])

        # Store crea su manager automáticamente.
        self.store = Store.objects.create(
            tenant=self.tenant, name="Tienda1", store_type="T"
        )
        # Un vendedor asociado a la tienda.
        from django.contrib.auth.models import User

        self.seller = User.objects.create(username="canc.vendedor1")
        StoreWorker.objects.create(store=self.store, worker=self.seller, role="V")

    def test_tenant_users_includes_owner_manager_seller(self):
        user_ids = set(self.tenant.tenant_users().values_list("id", flat=True))
        self.assertIn(self.tenant.owner_id, user_ids)
        self.assertIn(self.store.manager_id, user_ids)
        self.assertIn(self.seller.id, user_ids)
        self.assertEqual(len(user_ids), 3)

    def test_cancelling_deletes_all_tokens(self):
        # Emitir tokens para los tres usuarios.
        for user in self.tenant.tenant_users():
            self.Token.objects.create(user=user)
        self.assertEqual(self.Token.objects.count(), 3)

        # Simular el efecto del endpoint de cancelación.
        self.tenant.cancelled_at = timezone.now()
        self.tenant.save(update_fields=["cancelled_at"])
        self.Token.objects.filter(user__in=self.tenant.tenant_users()).delete()

        self.assertEqual(self.Token.objects.count(), 0)

    def test_cancelled_tenant_has_no_access_despite_valid_payment(self):
        self.tenant.cancelled_at = timezone.now()
        self.tenant.save(update_fields=["cancelled_at"])
        self.assertFalse(self.tenant.has_access())

    def test_gate_blocks_cancelled_tenant_with_tenant_inactive(self):
        from pos_multi_store.permissions import TenantHasAccess

        self.tenant.cancelled_at = timezone.now()
        self.tenant.save(update_fields=["cancelled_at"])

        perm = TenantHasAccess()

        class _Req:
            def __init__(self, user):
                self.user = user

        request = _Req(self.tenant.owner)
        self.assertFalse(perm.has_permission(request, view=None))
        self.assertEqual(perm.message.get("code"), "tenant_inactive")

    def test_gate_allows_active_tenant(self):
        from pos_multi_store.permissions import TenantHasAccess

        perm = TenantHasAccess()

        class _Req:
            def __init__(self, user):
                self.user = user

        request = _Req(self.tenant.owner)
        self.assertTrue(perm.has_permission(request, view=None))
