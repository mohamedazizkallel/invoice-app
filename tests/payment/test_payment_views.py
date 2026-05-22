import pytest
from decimal import Decimal
from unittest.mock import patch
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestProcessPayment:
    def _make_invoice_with_total(self, seller, total_approx):
        """Helper: create an invoice with a service priced to hit roughly `total_approx`."""
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        unit_price = (total_approx - Decimal('1.000')) / Decimal('1.19')
        InvoiceServiceFactory(invoice=invoice, unit_price=unit_price.quantize(Decimal('0.001')))
        return invoice

    def test_process_payment_partial(self, tenant, seller, logged_in_client):
        invoice = self._make_invoice_with_total(seller, Decimal('500.000'))
        resp = logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': '100.000',
        })
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('100.000')
        assert invoice.status == 'CURRENT'

    def test_process_payment_full(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        total = invoice.calculate_total()
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': str(total),
        })
        invoice.refresh_from_db()
        assert invoice.status == 'PAID'

    def test_process_payment_clamps_to_remaining(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        total = invoice.calculate_total()
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': str(total + Decimal('999.000')),
        })
        invoice.refresh_from_db()
        assert invoice.amount_paid == total

    def test_process_payment_zero_amount(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        resp = logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': '0',
        })
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('0.000')

    def test_process_payment_with_credit_notes(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory, CreditNoteFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))
        CreditNoteFactory(client=invoice.client, invoice=invoice, amount_ht=Decimal('100.000'), tva=19)
        total = invoice.calculate_total()
        cn_total = invoice.get_credit_notes_total()
        effective = total - cn_total
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': str(effective),
        })
        invoice.refresh_from_db()
        assert invoice.status == 'PAID'

    def test_process_payment_with_auto_retenu(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        from unittest.mock import patch
        seller.default_retenu_rate = Decimal('1.5')
        with patch('sales.models._sync_ngsign_org'):
            seller.save()
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('2000.000'))
        total = invoice.calculate_total()
        auto_retenu = invoice.get_auto_retenu_amount()
        assert auto_retenu > Decimal('0')
        effective = total - auto_retenu
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': str(effective),
        })
        invoice.refresh_from_db()
        assert invoice.status == 'PAID'

    def test_process_payment_creates_ledger_credit(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        from sales.models import ClientTransaction
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': '50.000',
        })
        txn = ClientTransaction.objects.filter(
            invoice=invoice, transaction_type='CREDIT', source='INVOICE_PAID'
        ).first()
        assert txn is not None
        assert txn.amount == Decimal('50.000')


@pytest.mark.django_db(transaction=True)
class TestRetenuAjax:
    def test_get_retenu_rate_json(self, tenant, seller, logged_in_client):
        from tests.factories import RetenuFactory
        retenu = RetenuFactory(
            category='LOYERS',
            subcategory='LOYER_RESIDENT',
            rate=Decimal('10.00'),
        )
        resp = logged_in_client.get(reverse('get_retenu_rate', args=[retenu.id]))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['rate'] == 10.0

    def test_calculate_retenu_preview(self, tenant, seller, logged_in_client):
        from tests.factories import RetenuFactory
        retenu = RetenuFactory(rate=Decimal('5.00'))
        resp = logged_in_client.get(reverse('calculate_retenu_preview'), {
            'retenu_id': retenu.id,
            'base_amount': '2000.000',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['calculated_amount'] == 100.0
