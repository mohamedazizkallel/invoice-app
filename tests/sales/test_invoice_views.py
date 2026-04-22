import pytest
from decimal import Decimal
from unittest.mock import patch
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestInvoiceViews:
    def test_invoice_list_requires_login(self, tenant, seller):
        from django.test import Client
        client = Client()
        resp = client.get(reverse('invoices_list'))
        assert resp.status_code == 302
        assert resp.url == '/' or resp.url.startswith('/?next=')

    def test_invoice_list_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('invoices_list'))
        assert resp.status_code == 200

    def test_invoice_list_search(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory
        inv = InvoiceFactory(title='Special Invoice')
        resp = logged_in_client.get(reverse('invoices_list'), {'search': 'Special'})
        assert resp.status_code == 200

    def test_invoice_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        client = ClientFactory()
        service = ServiceFactory()
        resp = logged_in_client.post(reverse('invoice_create'), {
            'client': client.id,
            'service_id[]': [service.id],
            'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'],
            'tva': '19',
            'timbre_fiscal': '1.000',
            'discount': '0',
        })
        assert resp.status_code == 302
        from sales.models import Invoice
        assert Invoice.objects.filter(client=client).exists()

    def test_invoice_create_no_client(self, tenant, seller, logged_in_client):
        resp = logged_in_client.post(reverse('invoice_create'), {})
        assert resp.status_code == 302

    def test_invoice_create_no_services(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        client = ClientFactory()
        resp = logged_in_client.post(reverse('invoice_create'), {
            'client': client.id,
        })
        assert resp.status_code == 302

    def test_invoice_create_ledger_debit(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import ClientTransaction
        client = ClientFactory()
        service = ServiceFactory()
        logged_in_client.post(reverse('invoice_create'), {
            'client': client.id,
            'service_id[]': [service.id],
            'unit_price[]': ['1000.000'],
            'has_fodec[]': ['0'],
            'tva': '19',
            'timbre_fiscal': '1.000',
            'discount': '0',
        })
        txn = ClientTransaction.objects.filter(client=client, transaction_type='DEBIT').first()
        assert txn is not None
        assert txn.source == 'INVOICE_CREATED'

    def test_invoice_detail_renders(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()
        resp = logged_in_client.get(reverse('invoice_detail', args=[invoice.id]))
        assert resp.status_code == 200

    def test_invoice_edit_updates_fields(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ServiceFactory
        invoice = InvoiceFactory()
        service = ServiceFactory()
        resp = logged_in_client.post(reverse('invoice_edit', args=[invoice.id]), {
            'status': 'CONFIRMED',
            'notes': 'Updated note',
            'tva': '19',
            'timbre_fiscal': '1.000',
            'discount': '5',
            'client': invoice.client.id,
            'service_id[]': [service.id],
            'unit_price[]': ['200.000'],
            'has_fodec[]': ['0'],
        })
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.status == 'CONFIRMED'
        assert invoice.notes == 'Updated note'

    def test_invoice_delete_removes_ledger(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ClientTransactionFactory
        invoice = InvoiceFactory()
        ClientTransactionFactory(client=invoice.client, invoice=invoice, transaction_type='DEBIT')
        logged_in_client.post(reverse('invoice_delete', args=[invoice.id]))
        from sales.models import ClientTransaction, Invoice
        assert not Invoice.objects.filter(pk=invoice.pk).exists()
        assert not ClientTransaction.objects.filter(invoice=invoice).exists()

    def test_invoice_delete_post_only(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()
        resp = logged_in_client.get(reverse('invoice_delete', args=[invoice.id]))
        assert resp.status_code == 302
        from sales.models import Invoice
        assert Invoice.objects.filter(pk=invoice.pk).exists()

    def test_invoice_create_with_manual_number(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        resp = logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_number': '42',
        })
        assert resp.status_code == 302
        inv = Invoice.objects.filter(client=c).first()
        assert inv is not None
        assert inv.uniqueId.startswith('FV-042-')

    def test_invoice_create_manual_number_conflict(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory, InvoiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        InvoiceFactory(client=c, uniqueId='FV-005-2026')
        before = Invoice.objects.count()
        resp = logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_number': '5',
        })
        assert resp.status_code == 302
        assert Invoice.objects.count() == before

    def test_invoice_create_with_manual_date(self, tenant, seller, logged_in_client):
        from datetime import date
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_date': '2025-06-15',
        })
        inv = Invoice.objects.filter(client=c).first()
        assert inv.date_created.date() == date(2025, 6, 15)
        assert inv.uniqueId.endswith('-2025')

    def test_invoice_create_default_date_is_today(self, tenant, seller, logged_in_client):
        from django.utils import timezone
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
        })
        inv = Invoice.objects.filter(client=c).first()
        assert inv.date_created.date() == timezone.localtime(timezone.now()).date()

    def test_invoice_edit_updates_date_and_number(self, tenant, seller, logged_in_client):
        from datetime import date
        from tests.factories import InvoiceFactory, ServiceFactory
        s = ServiceFactory()
        inv = InvoiceFactory(uniqueId='FV-001-2026', status='CURRENT', is_locked=False)
        resp = logged_in_client.post(reverse('invoice_edit', args=[inv.id]), {
            'client': inv.client.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'status': 'CURRENT',
            'invoice_number': '77', 'invoice_date': '2026-02-10',
        })
        assert resp.status_code == 302
        inv.refresh_from_db()
        assert inv.uniqueId == 'FV-077-2026'
        assert inv.date_created.date() == date(2026, 2, 10)

    def test_invoice_edit_locked_ignores_date_number(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ServiceFactory
        s = ServiceFactory()
        inv = InvoiceFactory(uniqueId='FV-002-2026', status='CURRENT', is_locked=True)
        original_id = inv.uniqueId
        original_date = inv.date_created
        logged_in_client.post(reverse('invoice_edit', args=[inv.id]), {
            'client': inv.client.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'status': 'CURRENT',
            'invoice_number': '99', 'invoice_date': '2020-01-01',
        })
        inv.refresh_from_db()
        assert inv.uniqueId == original_id
        assert inv.date_created == original_date

    def test_invoice_edit_paid_ignores_date_number(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ServiceFactory
        s = ServiceFactory()
        inv = InvoiceFactory(uniqueId='FV-003-2026', status='PAID', is_locked=False)
        original_id = inv.uniqueId
        logged_in_client.post(reverse('invoice_edit', args=[inv.id]), {
            'client': inv.client.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'status': 'PAID',
            'invoice_number': '88',
        })
        inv.refresh_from_db()
        assert inv.uniqueId == original_id

    def test_invoice_edit_number_collision_rejected(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ServiceFactory
        s = ServiceFactory()
        InvoiceFactory(uniqueId='FV-050-2026')
        inv = InvoiceFactory(uniqueId='FV-004-2026', status='CURRENT', is_locked=False)
        logged_in_client.post(reverse('invoice_edit', args=[inv.id]), {
            'client': inv.client.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'status': 'CURRENT',
            'invoice_number': '50',
        })
        inv.refresh_from_db()
        assert inv.uniqueId == 'FV-004-2026'

    def test_invoice_create_sequence_after_manual_jump(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_number': '10', 'invoice_date': '2026-03-01',
        })
        logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_date': '2026-03-02',
        })
        ids = list(Invoice.objects.values_list('uniqueId', flat=True))
        assert 'FV-010-2026' in ids
        assert 'FV-011-2026' in ids
