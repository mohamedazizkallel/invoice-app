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

    def test_avoir_create_with_manual_number(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import CreditNote
        c = ClientFactory()
        resp = logged_in_client.post(reverse('avoir_create'), {
            'client': c.id, 'description': 'Test', 'amount_ht': '100.000', 'tva': '19',
            'invoice_number': '42',
        })
        assert resp.status_code == 302
        cn = CreditNote.objects.filter(client=c).first()
        assert cn is not None
        assert cn.uniqueId.startswith('AV-042-')

    def test_avoir_create_manual_number_conflict(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, CreditNoteFactory
        from sales.models import CreditNote
        c = ClientFactory()
        CreditNoteFactory(client=c, uniqueId='AV-005-2026')
        before = CreditNote.objects.count()
        logged_in_client.post(reverse('avoir_create'), {
            'client': c.id, 'description': 'X', 'amount_ht': '10.000', 'tva': '19',
            'invoice_number': '5',
        })
        assert CreditNote.objects.count() == before

    def test_avoir_create_with_manual_date(self, tenant, seller, logged_in_client):
        from datetime import date
        from tests.factories import ClientFactory
        from sales.models import CreditNote
        c = ClientFactory()
        logged_in_client.post(reverse('avoir_create'), {
            'client': c.id, 'description': 'X', 'amount_ht': '10.000', 'tva': '19',
            'invoice_date': '2025-06-15',
        })
        cn = CreditNote.objects.filter(client=c).first()
        assert cn.date_created.date() == date(2025, 6, 15)
        assert cn.uniqueId.endswith('-2025')

    def test_avoir_create_default_date_is_today(self, tenant, seller, logged_in_client):
        from django.utils import timezone
        from tests.factories import ClientFactory
        from sales.models import CreditNote
        c = ClientFactory()
        logged_in_client.post(reverse('avoir_create'), {
            'client': c.id, 'description': 'X', 'amount_ht': '10.000', 'tva': '19',
        })
        cn = CreditNote.objects.filter(client=c).first()
        assert cn.date_created.date() == timezone.localtime(timezone.now()).date()

    def test_avoir_edit_updates_date_and_number(self, tenant, seller, logged_in_client):
        from datetime import date
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory(uniqueId='AV-001-2026')
        logged_in_client.post(reverse('avoir_edit', args=[cn.id]), {
            'description': 'Updated', 'amount_ht': '20.000', 'tva': '19',
            'invoice_number': '77', 'invoice_date': '2026-02-10',
        })
        cn.refresh_from_db()
        assert cn.uniqueId == 'AV-077-2026'
        assert cn.date_created.date() == date(2026, 2, 10)

    def test_avoir_edit_number_collision_rejected(self, tenant, seller, logged_in_client):
        from tests.factories import CreditNoteFactory
        CreditNoteFactory(uniqueId='AV-050-2026')
        cn = CreditNoteFactory(uniqueId='AV-004-2026')
        logged_in_client.post(reverse('avoir_edit', args=[cn.id]), {
            'description': 'X', 'amount_ht': '10.000', 'tva': '19',
            'invoice_number': '50',
        })
        cn.refresh_from_db()
        assert cn.uniqueId == 'AV-004-2026'
