import pytest
from unittest.mock import patch
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestInvoiceElfatooraSubmitView:
    def test_submit_returns_ref(self, logged_in_client, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(signed_xml=b'<signed/>')
        url = reverse('invoice-elfatoora-submit', args=[gi.invoice.id])

        with patch('gov.elfatoora.service.client.save_efact', return_value='REF-9'):
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        assert resp.json()['generated_ref'] == 'REF-9'

    def test_submit_400_when_not_signed(self, logged_in_client, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(signed_xml=None)
        url = reverse('invoice-elfatoora-submit', args=[gi.invoice.id])
        resp = logged_in_client.post(url)
        assert resp.status_code == 400

    def test_submit_409_when_already_transmitted(self, logged_in_client, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(
            signed_xml=b'<signed/>',
            elfatoora_generated_ref='REF-PREV',
        )
        url = reverse('invoice-elfatoora-submit', args=[gi.invoice.id])
        resp = logged_in_client.post(url)
        assert resp.status_code == 409
        assert resp.json()['generated_ref'] == 'REF-PREV'


@pytest.mark.django_db(transaction=True)
class TestInvoiceElfatooraPollView:
    def test_poll_returns_status(self, logged_in_client, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(
            signed_xml=b'<signed/>',
            elfatoora_generated_ref='REF-1',
            elfatoora_status='SUBMITTED',
        )
        url = reverse('invoice-elfatoora-poll', args=[gi.invoice.id])
        with patch('gov.elfatoora.service.client.consult_efact', return_value=[]):
            resp = logged_in_client.post(url)
        assert resp.status_code == 200
        assert resp.json()['success'] is True

    def test_poll_400_when_no_ref(self, logged_in_client, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(elfatoora_generated_ref=None)
        url = reverse('invoice-elfatoora-poll', args=[gi.invoice.id])
        resp = logged_in_client.post(url)
        assert resp.status_code == 400


@pytest.mark.django_db(transaction=True)
class TestAvoirElfatooraViews:
    def test_avoir_submit(self, logged_in_client, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(use_credit_note=True, signed_xml=b'<signed/>')
        url = reverse('avoir-elfatoora-submit', args=[gi.credit_note.id])
        with patch('gov.elfatoora.service.client.save_efact', return_value='REF-A'):
            resp = logged_in_client.post(url)
        assert resp.status_code == 200
        assert resp.json()['generated_ref'] == 'REF-A'

    def test_avoir_poll(self, logged_in_client, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(
            use_credit_note=True,
            signed_xml=b'<signed/>',
            elfatoora_generated_ref='REF-1',
        )
        url = reverse('avoir-elfatoora-poll', args=[gi.credit_note.id])
        with patch('gov.elfatoora.service.client.consult_efact', return_value=[]):
            resp = logged_in_client.post(url)
        assert resp.status_code == 200
