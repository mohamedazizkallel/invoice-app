import pytest
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command


@pytest.mark.django_db(transaction=True)
class TestPollElfatooraCommand:
    @pytest.fixture(autouse=True)
    def _clean_gov(self, tenant):
        from gov.models import GovInvoice
        GovInvoice.objects.all().delete()
        yield
        GovInvoice.objects.all().delete()

    def test_polls_pending_invoices_for_schema(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(
            signed_xml=b'<signed/>',
            elfatoora_generated_ref='REF-1',
            elfatoora_status='SUBMITTED',
        )
        out = StringIO()

        with patch('gov.elfatoora.service.client.consult_efact', return_value=[]):
            call_command(
                'poll_elfatoora', schema=tenant.schema_name, stdout=out
            )

        assert '1 pending invoice' in out.getvalue()
        assert 'polled=1' in out.getvalue()

    def test_dry_run_skips_writes(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(
            signed_xml=b'<signed/>',
            elfatoora_generated_ref='REF-1',
            elfatoora_status='SUBMITTED',
        )
        out = StringIO()

        with patch('gov.elfatoora.service.client.consult_efact') as m:
            call_command(
                'poll_elfatoora', schema=tenant.schema_name, dry_run=True, stdout=out
            )

        m.assert_not_called()
        assert 'would poll' in out.getvalue()

    def test_skips_non_submitted(self, tenant, seller, elfatoora_account):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(
            signed_xml=b'<signed/>',
            elfatoora_status='ACKNOWLEDGED',
        )
        out = StringIO()

        with patch('gov.elfatoora.service.client.consult_efact') as m:
            call_command(
                'poll_elfatoora', schema=tenant.schema_name, stdout=out
            )

        m.assert_not_called()
        assert '0 pending invoice' in out.getvalue()
