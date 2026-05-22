import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestClientViews:
    def test_clients_list_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('clients'))
        assert resp.status_code == 200

    def test_clients_list_search(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        ClientFactory(clientname='UniqueSearchName')
        resp = logged_in_client.get(reverse('clients'), {'search': 'UniqueSearchName'})
        assert resp.status_code == 200

    def test_edit_client_updates_fields(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        client = ClientFactory()
        logged_in_client.post(reverse('edit_client', args=[client.id]), {
            'clientname': 'Updated Name',
            'emailAddress': 'new@test.com',
            'adress': 'New Address',
            'mf': 'NEWMF123',
        })
        client.refresh_from_db()
        assert client.clientname == 'Updated Name'

    def test_delete_client(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import Client
        client = ClientFactory()
        logged_in_client.get(reverse('delete-client', args=[client.pk]))
        assert not Client.objects.filter(pk=client.pk).exists()

    def test_client_add_transaction_manual(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import ClientTransaction
        client = ClientFactory()
        logged_in_client.post(reverse('client_add_transaction', args=[client.id]), {
            'transaction_type': 'DEBIT',
            'amount': '250.000',
            'description': 'Manual debit',
        })
        txn = ClientTransaction.objects.filter(client=client).first()
        assert txn is not None
        assert txn.source == 'MANUAL'
        assert txn.amount == Decimal('250.000')

    def test_client_add_credit_updates_invoice_paid(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, InvoiceFactory, InvoiceServiceFactory
        client = ClientFactory()
        invoice = InvoiceFactory(client=client, tva=19, discount=0)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))
        logged_in_client.post(reverse('client_add_transaction', args=[client.id]), {
            'transaction_type': 'CREDIT',
            'amount': '500.000',
            'description': 'Partial payment',
            'invoice_id': invoice.id,
        })
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('500.000')

    def test_client_add_credit_marks_paid(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, InvoiceFactory, InvoiceServiceFactory
        client = ClientFactory()
        invoice = InvoiceFactory(client=client, tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        total = invoice.calculate_total()
        logged_in_client.post(reverse('client_add_transaction', args=[client.id]), {
            'transaction_type': 'CREDIT',
            'amount': str(total),
            'description': 'Full payment',
            'invoice_id': invoice.id,
        })
        invoice.refresh_from_db()
        assert invoice.status == 'PAID'

    def test_client_delete_transaction(self, tenant, seller, logged_in_client):
        from tests.factories import ClientTransactionFactory
        txn = ClientTransactionFactory()
        resp = logged_in_client.post(reverse('client_delete_transaction', args=[txn.id]))
        assert resp.status_code == 200
        from sales.models import ClientTransaction
        assert not ClientTransaction.objects.filter(pk=txn.pk).exists()

    def test_client_unpaid_invoices_json(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, InvoiceFactory
        client = ClientFactory()
        InvoiceFactory(client=client, status='CURRENT')
        resp = logged_in_client.get(reverse('client_unpaid_invoices', args=[client.id]))
        assert resp.status_code == 200

    def test_mf_map_returns_json(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        ClientFactory(mf='TESTMF999')
        resp = logged_in_client.get(reverse('mf_map'))
        assert resp.status_code == 200
