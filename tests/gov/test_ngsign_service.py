import pytest
from unittest.mock import patch, MagicMock
from gov.ngsign.exceptions import (
    NGSignNotConfiguredError, NGSignAPIError, NGSignSubmissionError
)


@pytest.mark.django_db(transaction=True)
class TestSubmitInvoice:
    def test_calls_build_payload_and_create_transaction(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        fake_txn = {
            'uuid': 'txn-uuid-1',
            'invoices': [{'uuid': 'inv-uuid-1', 'status': 'CREATED'}],
        }

        with patch('gov.ngsign.service.serializer.build_payload', return_value={'payload': 'data'}) as mock_payload, \
             patch('gov.ngsign.service.client.create_transaction', return_value=fake_txn) as mock_create:
            from gov.ngsign.service import submit_invoice
            submit_invoice(gov_invoice)

            mock_payload.assert_called_once_with(gov_invoice)
            mock_create.assert_called_once_with(
                ngsign_account.org_jwt,
                [{'payload': 'data'}],
                signer_email=ngsign_account.signer_email,
            )

    def test_stores_transaction_and_invoice_uuids(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        fake_txn = {
            'uuid': 'txn-uuid-42',
            'invoices': [{'uuid': 'inv-uuid-42', 'status': 'CREATED'}],
        }

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}), \
             patch('gov.ngsign.service.client.create_transaction', return_value=fake_txn):
            from gov.ngsign.service import submit_invoice
            submit_invoice(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_transaction_uuid == 'txn-uuid-42'
        assert gov_invoice.ngsign_invoice_uuid == 'inv-uuid-42'

    def test_sets_status_from_response(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        fake_txn = {
            'uuid': 'txn-1',
            'invoices': [{'uuid': 'inv-1', 'status': 'CONFIGURED'}],
        }

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}), \
             patch('gov.ngsign.service.client.create_transaction', return_value=fake_txn):
            from gov.ngsign.service import submit_invoice
            submit_invoice(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'CONFIGURED'

    def test_defaults_to_created_when_status_absent(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        fake_txn = {
            'uuid': 'txn-1',
            'invoices': [{'uuid': 'inv-1'}],  # no 'status' key
        }

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}), \
             patch('gov.ngsign.service.client.create_transaction', return_value=fake_txn):
            from gov.ngsign.service import submit_invoice
            submit_invoice(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'CREATED'

    def test_raises_not_configured_when_no_account(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        from gov.ngsign.service import submit_invoice
        with pytest.raises(NGSignNotConfiguredError):
            submit_invoice(gov_invoice)

    def test_raises_not_configured_when_no_signer_email(self, tenant, seller, ngsign_account):
        ngsign_account.signer_email = ''
        ngsign_account.save()

        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}):
            from gov.ngsign.service import submit_invoice
            with pytest.raises(NGSignNotConfiguredError, match='signer_email'):
                submit_invoice(gov_invoice)

    def test_raises_not_configured_when_account_error(self, tenant, seller, ngsign_account):
        ngsign_account.status = 'ERROR'
        ngsign_account.save()

        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        from gov.ngsign.service import submit_invoice
        with pytest.raises(NGSignNotConfiguredError):
            submit_invoice(gov_invoice)

    def test_sets_error_on_api_failure(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}), \
             patch('gov.ngsign.service.client.create_transaction', side_effect=NGSignAPIError('API down')):
            from gov.ngsign.service import submit_invoice
            with pytest.raises(NGSignSubmissionError):
                submit_invoice(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'ERROR'


@pytest.mark.django_db(transaction=True)
class TestCheckStatus:
    def test_updates_ngsign_status(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            ngsign_status='CREATED',
            ngsign_invoice_uuid='inv-uuid-1',
        )

        with patch('gov.ngsign.service.client.check_invoice_status',
                   return_value={'status': 'SIGNED', 'ttnReference': ''}):
            from gov.ngsign.service import check_status
            check_status(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'SIGNED'

    def test_fetches_signed_xml_on_ttn_signed(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            ngsign_status='SIGNED',
            ngsign_invoice_uuid='inv-uuid-1',
        )

        with patch('gov.ngsign.service.client.check_invoice_status',
                   return_value={'status': 'TTN_SIGNED'}), \
             patch('gov.ngsign.service.client.get_signed_xml',
                   return_value=b'<signed-xml/>') as mock_get:
            from gov.ngsign.service import check_status
            check_status(gov_invoice)

        mock_get.assert_called_once()
        gov_invoice.refresh_from_db()
        assert bytes(gov_invoice.signed_xml) == b'<signed-xml/>'
        assert gov_invoice.status == 'signed'

    def test_fetches_signed_xml_on_ttn_transfered(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            ngsign_status='SIGNED',
            ngsign_invoice_uuid='inv-uuid-1',
        )

        with patch('gov.ngsign.service.client.check_invoice_status',
                   return_value={'status': 'TTN_TRANSFERED'}), \
             patch('gov.ngsign.service.client.get_signed_xml',
                   return_value=b'<signed/>'):
            from gov.ngsign.service import check_status
            check_status(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'TTN_TRANSFERED'

    def test_raises_not_configured_when_no_account(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_invoice_uuid='inv-1')

        from gov.ngsign.service import check_status
        with pytest.raises(NGSignNotConfiguredError):
            check_status(gov_invoice)


@pytest.mark.django_db(transaction=True)
class TestGetAccount:
    def test_returns_account_for_current_tenant(self, tenant, ngsign_account):
        from gov.ngsign.service import _get_account
        account = _get_account()
        assert account is not None
        assert account.id == ngsign_account.id

    def test_returns_none_when_no_account(self, tenant):
        from gov.ngsign.service import _get_account
        assert _get_account() is None
