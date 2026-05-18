import pytest
from datetime import datetime, timezone as tz
from types import SimpleNamespace
from unittest.mock import patch

from gov.elfatoora.client import ElfatooraError
from gov.elfatoora.service import (
    ElfatooraNotReadyError, ElfatooraNotConfiguredError, submit, poll,
)


@pytest.mark.django_db(transaction=True)
class TestSubmit:
    def test_calls_save_efact_with_signed_xml(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(signed_xml=b'<signed/>')

        with patch('gov.elfatoora.service.client.save_efact',
                   return_value='REF-123') as m:
            submit(gi)

        m.assert_called_once_with(
            elfatoora_account.username,
            elfatoora_account.password,
            elfatoora_account.mf,
            b'<signed/>',
        )

    def test_stores_generated_ref_and_status(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(signed_xml=b'<signed/>')

        with patch('gov.elfatoora.service.client.save_efact',
                   return_value='REF-XYZ'):
            submit(gi)

        gi.refresh_from_db()
        assert gi.elfatoora_generated_ref == 'REF-XYZ'
        assert gi.elfatoora_status == 'SUBMITTED'
        assert gi.elfatoora_submitted_at is not None
        assert gi.status == 'sent'

    def test_raises_when_signed_xml_missing(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(signed_xml=None)

        with pytest.raises(ElfatooraNotReadyError):
            submit(gi)

    def test_raises_when_account_missing(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(signed_xml=b'<signed/>')

        with pytest.raises(ElfatooraNotConfiguredError):
            submit(gi)

    def test_raises_when_account_status_error(self, tenant, seller, elfatoora_account):
        elfatoora_account.status = 'ERROR'
        elfatoora_account.save()

        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(signed_xml=b'<signed/>')

        with pytest.raises(ElfatooraNotConfiguredError):
            submit(gi)

    def test_records_error_on_soap_failure(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(signed_xml=b'<signed/>')

        with patch('gov.elfatoora.service.client.save_efact',
                   side_effect=ElfatooraError('boom')):
            with pytest.raises(ElfatooraError):
                submit(gi)

        gi.refresh_from_db()
        assert gi.elfatoora_status == 'ERROR'
        assert 'boom' in gi.elfatoora_last_error


@pytest.mark.django_db(transaction=True)
class TestPoll:
    def _result(self, errors=()):
        ack = SimpleNamespace(
            dateAck=datetime(2026, 5, 18, 12, 0, 0, tzinfo=tz.utc),
            errors=list(errors),
        )
        return [SimpleNamespace(listAcknowlegments=[ack])]

    def test_marks_acknowledged_when_no_errors(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(
            signed_xml=b'<signed/>',
            elfatoora_generated_ref='REF-1',
            elfatoora_status='SUBMITTED',
        )

        with patch('gov.elfatoora.service.client.consult_efact',
                   return_value=self._result()):
            poll(gi)

        gi.refresh_from_db()
        assert gi.elfatoora_status == 'ACKNOWLEDGED'
        assert gi.status == 'accepted'
        assert gi.elfatoora_last_ack_at is not None

    def test_marks_rejected_when_errors_present(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(
            signed_xml=b'<signed/>',
            elfatoora_generated_ref='REF-1',
            elfatoora_status='SUBMITTED',
        )
        err = SimpleNamespace(errorId=42, errorDescription='bad MF')

        with patch('gov.elfatoora.service.client.consult_efact',
                   return_value=self._result(errors=[err])):
            poll(gi)

        gi.refresh_from_db()
        assert gi.elfatoora_status == 'REJECTED'
        assert gi.status == 'rejected'
        assert '42' in gi.elfatoora_last_error
        assert 'bad MF' in gi.elfatoora_last_error

    def test_raises_when_no_generated_ref(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(elfatoora_generated_ref=None)

        with pytest.raises(ElfatooraNotReadyError):
            poll(gi)

    def test_handles_empty_results(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        gi = GovInvoiceFactory(elfatoora_generated_ref='REF-1')

        with patch('gov.elfatoora.service.client.consult_efact', return_value=[]):
            result = poll(gi)

        assert result == []
