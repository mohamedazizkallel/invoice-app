import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestPurchaseViews:
    def test_purchase_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory, SupplyFactory
        from sales.models import Purchase
        supplier = SupplierFactory()
        supply = SupplyFactory()
        resp = logged_in_client.post(reverse('purchase_create'), {
            'supplier': supplier.id,
            'supply_id[]': [supply.id],
            'quantity[]': ['5.000'],
            'line_unit_price[]': ['10.000'],
            'tva': '19.00',
            'discount': '0.00',
            'timbre_fiscal': '1.000',
        })
        assert resp.status_code == 302
        assert Purchase.objects.filter(supplier=supplier).exists()

    def test_purchase_confirm_increments_stock(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory, SupplyFactory
        supply = SupplyFactory(stock_quantity=Decimal('100.000'))
        purchase = PurchaseFactory(status='DRAFT')
        PurchaseLineFactory(purchase=purchase, supply=supply, quantity=Decimal('20.000'))
        logged_in_client.post(reverse('purchase_confirm', args=[purchase.id]))
        supply.refresh_from_db()
        assert supply.stock_quantity == Decimal('120.000')

    def test_purchase_confirm_creates_supplier_credit(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        from sales.models import SupplierTransaction
        purchase = PurchaseFactory(status='DRAFT')
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('1000.000'))
        logged_in_client.post(reverse('purchase_confirm', args=[purchase.id]))
        txn = SupplierTransaction.objects.filter(purchase=purchase, transaction_type='CREDIT').first()
        assert txn is not None
        assert txn.source == 'PURCHASE_CONFIRMED'

    def test_purchase_confirm_sets_received(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory(status='DRAFT')
        PurchaseLineFactory(purchase=purchase)
        logged_in_client.post(reverse('purchase_confirm', args=[purchase.id]))
        purchase.refresh_from_db()
        assert purchase.status == 'RECEIVED'

    def test_purchase_confirm_already_paid(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory
        purchase = PurchaseFactory(status='PAID')
        resp = logged_in_client.post(reverse('purchase_confirm', args=[purchase.id]))
        assert resp.status_code == 302
        purchase.refresh_from_db()
        assert purchase.status == 'PAID'

    def test_purchase_payment_creates_debit(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        from sales.models import SupplierTransaction
        purchase = PurchaseFactory(status='RECEIVED')
        PurchaseLineFactory(purchase=purchase)
        logged_in_client.post(reverse('process_purchase_payment', args=[purchase.id]))
        txn = SupplierTransaction.objects.filter(purchase=purchase, transaction_type='DEBIT').first()
        assert txn is not None
        assert txn.source == 'PURCHASE_PAID'

    def test_purchase_payment_sets_paid(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory(status='RECEIVED')
        PurchaseLineFactory(purchase=purchase)
        logged_in_client.post(reverse('process_purchase_payment', args=[purchase.id]))
        purchase.refresh_from_db()
        assert purchase.status == 'PAID'

    def test_purchase_payment_already_paid(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory
        purchase = PurchaseFactory(status='PAID')
        resp = logged_in_client.post(reverse('process_purchase_payment', args=[purchase.id]))
        assert resp.status_code == 302

    def test_purchase_delete(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory
        from sales.models import Purchase
        purchase = PurchaseFactory()
        logged_in_client.post(reverse('purchase_delete', args=[purchase.id]))
        assert not Purchase.objects.filter(pk=purchase.pk).exists()
