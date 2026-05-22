import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestInvoiceNgsignSubmit:
    def test_creates_gov_invoice_with_submitting_status(self, logged_in_client, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        with patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()
            url = reverse('invoice-ngsign-submit', args=[invoice.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True

        from gov.models import GovInvoice
        gov = GovInvoice.objects.get(invoice=invoice)
        assert gov.ngsign_status == 'SUBMITTING'
        assert gov.submitted_at is not None

    def test_duplicate_returns_409(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_status='SUBMITTING')

        url = reverse('invoice-ngsign-submit', args=[gov_invoice.invoice.id])
        resp = logged_in_client.post(url)

        assert resp.status_code == 409
        assert resp.json()['success'] is False

    def test_resets_non_submitting_status(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_status='ERROR', notes='old error')

        with patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()
            url = reverse('invoice-ngsign-submit', args=[gov_invoice.invoice.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'SUBMITTING'
        assert gov_invoice.notes == ''

    def test_nonexistent_returns_404(self, logged_in_client, tenant, seller):
        url = reverse('invoice-ngsign-submit', args=[99999])
        resp = logged_in_client.post(url)
        assert resp.status_code == 404

    def test_spawns_thread(self, logged_in_client, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        with patch('threading.Thread') as mock_thread:
            mock_instance = MagicMock()
            mock_thread.return_value = mock_instance
            url = reverse('invoice-ngsign-submit', args=[invoice.id])
            logged_in_client.post(url)

        mock_thread.assert_called_once()
        mock_instance.start.assert_called_once()

    def test_requires_login(self, tenant):
        from django.test import Client
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        anon_client = Client()
        url = reverse('invoice-ngsign-submit', args=[invoice.id])
        resp = anon_client.post(url)
        assert resp.status_code == 302

    def test_requires_post(self, logged_in_client, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        url = reverse('invoice-ngsign-submit', args=[invoice.id])
        resp = logged_in_client.get(url)
        assert resp.status_code == 405


@pytest.mark.django_db(transaction=True)
class TestAvoirNgsignSubmit:
    def test_creates_gov_invoice(self, logged_in_client, tenant, seller):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory()

        with patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()
            url = reverse('avoir-ngsign-submit', args=[cn.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        from gov.models import GovInvoice
        gov = GovInvoice.objects.get(credit_note=cn)
        assert gov.ngsign_status == 'SUBMITTING'

    def test_duplicate_returns_409(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(use_credit_note=True, ngsign_status='SUBMITTING')

        url = reverse('avoir-ngsign-submit', args=[gov_invoice.credit_note.id])
        resp = logged_in_client.post(url)
        assert resp.status_code == 409


@pytest.mark.django_db(transaction=True)
class TestProcessNgsignSubmission:
    def test_sets_error_on_exception(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_status='SUBMITTING')

        # Don't mock set_schema — the function needs it to access the tenant DB.
        # Only mock connection.close to prevent closing the test's connection.
        with patch('gov.ngsign.service.submit_invoice', side_effect=Exception('API failure')), \
             patch('django.db.connection.close'):
            from sales.views import _process_ngsign_submission
            _process_ngsign_submission(gov_invoice.id, 'test_tenant')

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'ERROR'
        assert 'API failure' in gov_invoice.notes

    def test_closes_connection(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_status='SUBMITTING')

        with patch('gov.ngsign.service.submit_invoice'), \
             patch('django.db.connection.close') as mock_close:
            from sales.views import _process_ngsign_submission
            _process_ngsign_submission(gov_invoice.id, 'test_tenant')

        mock_close.assert_called_once()

    def test_generates_xml_for_invoice(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(unsigned_xml=b'', ngsign_status='SUBMITTING')

        with patch('gov.ngsign.service.submit_invoice'), \
             patch('gov.teif.builder.build_unsigned_teif', return_value=b'<TEIF>gen</TEIF>') as mock_build, \
             patch('django.db.connection.close'):
            from sales.views import _process_ngsign_submission
            _process_ngsign_submission(gov_invoice.id, 'test_tenant')

        mock_build.assert_called_once()

    def test_generates_xml_for_avoir(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            use_credit_note=True, unsigned_xml=b'', ngsign_status='SUBMITTING'
        )

        with patch('gov.ngsign.service.submit_invoice'), \
             patch('gov.teif.builder.build_unsigned_teif_avoir', return_value=b'<TEIF>av</TEIF>') as mock_build, \
             patch('django.db.connection.close'):
            from sales.views import _process_ngsign_submission
            _process_ngsign_submission(gov_invoice.id, 'test_tenant')

        mock_build.assert_called_once()


@pytest.mark.django_db(transaction=True)
class TestInvoiceNgsignCheck:
    def test_returns_status_on_success(self, logged_in_client, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            ngsign_status='CREATED', ngsign_invoice_uuid='inv-uuid-1'
        )

        with patch('gov.ngsign.service.check_status',
                   return_value={'status': 'SIGNED', 'ttnReference': 'TTN-001'}):
            url = reverse('invoice-ngsign-check', args=[gov_invoice.invoice.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert 'ngsign_status' in data

    def test_not_submitted_returns_400(self, logged_in_client, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        url = reverse('invoice-ngsign-check', args=[invoice.id])
        resp = logged_in_client.post(url)
        assert resp.status_code == 400

    def test_api_error_returns_500(self, logged_in_client, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        from gov.ngsign.exceptions import NGSignAPIError
        gov_invoice = GovInvoiceFactory(
            ngsign_status='CREATED', ngsign_invoice_uuid='inv-uuid-1'
        )

        with patch('gov.ngsign.service.check_status', side_effect=NGSignAPIError('timeout')):
            url = reverse('invoice-ngsign-check', args=[gov_invoice.invoice.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 500


@pytest.mark.django_db(transaction=True)
class TestAvoirNgsignCheck:
    def test_returns_status(self, logged_in_client, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            use_credit_note=True,
            ngsign_status='CREATED',
            ngsign_invoice_uuid='inv-uuid-1',
        )

        with patch('gov.ngsign.service.check_status',
                   return_value={'status': 'SIGNED', 'ttnReference': ''}):
            url = reverse('avoir-ngsign-check', args=[gov_invoice.credit_note.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        assert resp.json()['success'] is True

    def test_not_submitted_returns_400(self, logged_in_client, tenant, seller):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory()

        url = reverse('avoir-ngsign-check', args=[cn.id])
        resp = logged_in_client.post(url)
        assert resp.status_code == 400


@pytest.mark.django_db(transaction=True)
class TestCheckViewGuards:
    def test_invoice_check_requires_login(self, tenant):
        from django.test import Client
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        anon_client = Client()
        url = reverse('invoice-ngsign-check', args=[invoice.id])
        resp = anon_client.post(url)
        assert resp.status_code == 302

    def test_avoir_check_requires_login(self, tenant):
        from django.test import Client
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory()

        anon_client = Client()
        url = reverse('avoir-ngsign-check', args=[cn.id])
        resp = anon_client.post(url)
        assert resp.status_code == 302
