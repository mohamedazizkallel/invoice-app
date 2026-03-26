import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestCreditNoteViews:
    def test_avoir_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import CreditNote, ClientTransaction
        client = ClientFactory()
        resp = logged_in_client.post(reverse('avoir_create'), {
            'client': client.id,
            'description': 'Test avoir',
            'amount_ht': '500.000',
            'tva': '19',
        })
        assert resp.status_code == 302
        assert CreditNote.objects.filter(client=client).exists()
        txn = ClientTransaction.objects.filter(client=client, source='AVOIR_CREATED').first()
        assert txn is not None
        assert txn.transaction_type == 'CREDIT'

    def test_avoir_create_no_description(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        client = ClientFactory()
        resp = logged_in_client.post(reverse('avoir_create'), {
            'client': client.id,
            'amount_ht': '500.000',
        })
        assert resp.status_code == 302
        from sales.models import CreditNote
        assert not CreditNote.objects.filter(client=client).exists()

    def test_avoir_create_no_amount(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        client = ClientFactory()
        resp = logged_in_client.post(reverse('avoir_create'), {
            'client': client.id,
            'description': 'Test',
        })
        assert resp.status_code == 302
        from sales.models import CreditNote
        assert not CreditNote.objects.filter(client=client).exists()

    def test_avoir_create_with_linked_invoice(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, InvoiceFactory
        client = ClientFactory()
        invoice = InvoiceFactory(client=client)
        logged_in_client.post(reverse('avoir_create'), {
            'client': client.id,
            'description': 'Linked avoir',
            'amount_ht': '100.000',
            'invoice_id': invoice.id,
        })
        from sales.models import CreditNote
        cn = CreditNote.objects.filter(client=client).first()
        assert cn is not None
        assert cn.invoice == invoice

    def test_avoir_delete_post_only(self, tenant, seller, logged_in_client):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory()
        resp = logged_in_client.get(reverse('avoir_delete', args=[cn.id]))
        from sales.models import CreditNote
        assert CreditNote.objects.filter(pk=cn.pk).exists()

    def test_avoir_detail_renders(self, tenant, seller, logged_in_client):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory()
        resp = logged_in_client.get(reverse('avoir_detail', args=[cn.id]))
        assert resp.status_code == 200
