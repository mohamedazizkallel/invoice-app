import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone


API_URL_NAME = 'ngsign-pending-api'


@pytest.mark.django_db(transaction=True)
class TestNgsignPendingApi:
    def test_empty_response(self, logged_in_client, tenant):
        url = reverse(API_URL_NAME)
        resp = logged_in_client.get(url)

        assert resp.status_code == 200
        data = resp.json()
        assert data == {'to_sign': [], 'errors': [], 'in_progress': [], 'total': 0}

    def test_groups_created_to_sign(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CREATED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        data = resp.json()
        assert len(data['to_sign']) == 1
        assert data['to_sign'][0]['status'] == 'CREATED'

    def test_groups_configured_to_sign(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CONFIGURED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['to_sign']) == 1

    def test_groups_error_to_errors(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='ERROR')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['errors']) == 1

    def test_groups_ttn_rejected_to_errors(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='TTN_REJECTED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['errors']) == 1

    def test_groups_ttn_nottransfered_to_errors(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='TTN_NOTTRANSFERED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['errors']) == 1

    def test_groups_fresh_submitting_to_in_progress(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        # Use a timestamp just 5 seconds ago — well within the 60s stale threshold
        GovInvoiceFactory(ngsign_status='SUBMITTING', submitted_at=timezone.now() - timedelta(seconds=5))

        resp = logged_in_client.get(reverse(API_URL_NAME))
        data = resp.json()
        assert len(data['in_progress']) == 1
        assert data['in_progress'][0]['status'] == 'SUBMITTING'

    def test_groups_signed_to_in_progress(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='SIGNED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['in_progress']) == 1

    def test_excludes_ttn_signed(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='TTN_SIGNED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert resp.json()['total'] == 0

    def test_excludes_ttn_transfered(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='TTN_TRANSFERED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert resp.json()['total'] == 0

    def test_excludes_cancelled(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CANCELLED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert resp.json()['total'] == 0

    def test_stale_submitting_promoted_to_error(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        stale_time = timezone.now() - timedelta(seconds=120)
        gov = GovInvoiceFactory(ngsign_status='SUBMITTING', submitted_at=stale_time)

        resp = logged_in_client.get(reverse(API_URL_NAME))
        data = resp.json()
        assert len(data['errors']) == 1
        assert data['errors'][0]['status'] == 'ERROR'

        # Verify DB was updated
        gov.refresh_from_db()
        assert gov.ngsign_status == 'ERROR'
        assert 'expirée' in gov.notes

    def test_response_fields_for_invoice(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory, InvoiceFactory, ClientFactory
        client = ClientFactory(clientname='ACME Corp')
        invoice = InvoiceFactory(client=client, uniqueId='FA-042-2026')
        gov = GovInvoiceFactory(
            invoice=invoice,
            ngsign_status='CREATED',
            ngsign_transaction_uuid='txn-uuid-abc',
        )

        resp = logged_in_client.get(reverse(API_URL_NAME))
        item = resp.json()['to_sign'][0]

        assert item['doc_type'] == 'invoice'
        assert item['doc_number'] == 'FA-042-2026'
        assert item['client_name'] == 'ACME Corp'
        assert 'txn-uuid-abc' in item['pds_url']
        assert f'/invoices/{invoice.id}/' in item['detail_url']

    def test_response_fields_for_avoir(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory, CreditNoteFactory, ClientFactory
        client = ClientFactory(clientname='Beta LLC')
        cn = CreditNoteFactory(client=client, uniqueId='AV-007-2026')
        gov = GovInvoiceFactory(
            use_credit_note=True,
            credit_note=cn,
            ngsign_status='CREATED',
            ngsign_transaction_uuid='txn-uuid-def',
        )

        resp = logged_in_client.get(reverse(API_URL_NAME))
        item = resp.json()['to_sign'][0]

        assert item['doc_type'] == 'avoir'
        assert item['doc_number'] == 'AV-007-2026'
        assert item['client_name'] == 'Beta LLC'

    def test_pds_url_null_when_no_uuid(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CREATED', ngsign_transaction_uuid=None)

        resp = logged_in_client.get(reverse(API_URL_NAME))
        item = resp.json()['to_sign'][0]
        assert item['pds_url'] is None

    def test_total_count(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CREATED')
        GovInvoiceFactory(ngsign_status='ERROR')
        GovInvoiceFactory(ngsign_status='SIGNED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        data = resp.json()
        assert data['total'] == 3
        assert data['total'] == len(data['to_sign']) + len(data['errors']) + len(data['in_progress'])

    def test_requires_login(self, tenant):
        from django.test import Client
        anon = Client()
        resp = anon.get(reverse(API_URL_NAME))
        assert resp.status_code == 302

    def test_rejects_post(self, logged_in_client, tenant):
        resp = logged_in_client.post(reverse(API_URL_NAME))
        assert resp.status_code == 405
