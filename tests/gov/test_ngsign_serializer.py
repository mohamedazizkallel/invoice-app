import base64
import pytest
from unittest.mock import patch


@pytest.mark.django_db(transaction=True)
class TestBuildPayload:
    def test_invoice_structure(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        with patch('gov.ngsign.serializer.render_invoice_pdf', return_value=b'%PDF-fake'):
            from gov.ngsign.serializer import build_payload
            result = build_payload(gov_invoice)

        assert 'invoiceFileB64' in result
        assert 'invoiceTIEF' in result
        assert 'invoiceNumber' in result
        assert 'clientEmail' in result
        assert 'configuration' in result
        assert result['configuration']['allPages'] is True

    def test_invoice_encodes_xml_b64(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(unsigned_xml=b'<TEIF>hello</TEIF>')

        with patch('gov.ngsign.serializer.render_invoice_pdf', return_value=b'%PDF'):
            from gov.ngsign.serializer import build_payload
            result = build_payload(gov_invoice)

        decoded = base64.b64decode(result['invoiceTIEF'])
        assert decoded == b'<TEIF>hello</TEIF>'

    def test_invoice_encodes_pdf_b64(self, tenant, seller):
        pdf_bytes = b'%PDF-1.4 fake pdf content'

        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        with patch('gov.ngsign.serializer.render_invoice_pdf', return_value=pdf_bytes):
            from gov.ngsign.serializer import build_payload
            result = build_payload(gov_invoice)

        decoded = base64.b64decode(result['invoiceFileB64'])
        assert decoded == pdf_bytes

    def test_invoice_number(self, tenant, seller):
        from tests.factories import GovInvoiceFactory, InvoiceFactory
        invoice = InvoiceFactory(uniqueId='FA-TEST-001')
        gov_invoice = GovInvoiceFactory(invoice=invoice)

        with patch('gov.ngsign.serializer.render_invoice_pdf', return_value=b'%PDF'):
            from gov.ngsign.serializer import build_payload
            result = build_payload(gov_invoice)

        assert result['invoiceNumber'] == 'FA-TEST-001'

    def test_avoir_structure(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(use_credit_note=True)

        with patch('gov.ngsign.serializer.render_avoir_pdf', return_value=b'%PDF'):
            from gov.ngsign.serializer import build_payload
            result = build_payload(gov_invoice)

        assert 'invoiceFileB64' in result
        assert 'invoiceTIEF' in result
        assert 'invoiceNumber' in result

    def test_avoir_uses_credit_note_fields(self, tenant, seller):
        from tests.factories import GovInvoiceFactory, CreditNoteFactory
        cn = CreditNoteFactory(uniqueId='AV-TEST-001')
        gov_invoice = GovInvoiceFactory(use_credit_note=True, credit_note=cn)

        with patch('gov.ngsign.serializer.render_avoir_pdf', return_value=b'%PDF'):
            from gov.ngsign.serializer import build_payload
            result = build_payload(gov_invoice)

        assert result['invoiceNumber'] == 'AV-TEST-001'

    def test_client_email_fallback(self, tenant, seller):
        from tests.factories import GovInvoiceFactory, InvoiceFactory, ClientFactory
        client = ClientFactory(emailAddress=None)
        invoice = InvoiceFactory(client=client)
        gov_invoice = GovInvoiceFactory(invoice=invoice)

        with patch('gov.ngsign.serializer.render_invoice_pdf', return_value=b'%PDF'):
            from gov.ngsign.serializer import build_payload
            result = build_payload(gov_invoice)

        assert result['clientEmail'] == ''
