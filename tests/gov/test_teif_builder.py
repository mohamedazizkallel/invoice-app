import pytest
from lxml import etree
from decimal import Decimal

# TEIF elements live in no namespace (matches TTN 1.8.9 XSD).
def _ns(tag):
    return tag


def _find(root, path):
    return root.find(path.replace('t:', ''))


def _findall(root, path):
    return root.findall(path.replace('t:', ''))


@pytest.mark.django_db(transaction=True)
class TestBuildUnsignedTeif:
    def test_produces_valid_xml(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory()
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))

        from gov.teif.builder import build_unsigned_teif
        xml_bytes = build_unsigned_teif(invoice, seller)

        root = etree.fromstring(xml_bytes)
        assert root.tag == _ns('TEIF')

    def test_root_has_namespace_and_version(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory()
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))

        from gov.teif.builder import build_unsigned_teif
        xml_bytes = build_unsigned_teif(invoice, seller)
        root = etree.fromstring(xml_bytes)

        assert root.get('version') == '1.8.9'
        assert root.get('controlingAgency') == 'TTN'

    def test_sender_receiver_mf_stripped(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory, ClientFactory
        client = ClientFactory(mf='1234/ABC/D/000')
        invoice = InvoiceFactory(client=client)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))

        from gov.teif.builder import build_unsigned_teif
        xml_bytes = build_unsigned_teif(invoice, seller)
        root = etree.fromstring(xml_bytes)

        sender = _find(root, './/t:MessageSenderIdentifier')
        receiver = _find(root, './/t:MessageRecieverIdentifier')

        assert '/' not in sender.text
        assert '/' not in receiver.text

    def test_bgm_doc_type_invoice(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory()
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))

        from gov.teif.builder import build_unsigned_teif
        xml_bytes = build_unsigned_teif(invoice, seller)
        root = etree.fromstring(xml_bytes)

        doc_type = _find(root, './/t:DocumentType')
        assert doc_type.get('code') == 'I-11'
        assert doc_type.text == 'Facture'

    def test_dtm_has_correct_date_format(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory()
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))

        from gov.teif.builder import build_unsigned_teif
        xml_bytes = build_unsigned_teif(invoice, seller)
        root = etree.fromstring(xml_bytes)

        date_text = _find(root, './/t:DateText')
        assert date_text.get('format') == 'ddMMyy'
        assert len(date_text.text) == 6  # ddMMyy format

    def test_line_items_match_services(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory()
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('200.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('300.000'))

        from gov.teif.builder import build_unsigned_teif
        xml_bytes = build_unsigned_teif(invoice, seller)
        root = etree.fromstring(xml_bytes)

        lins = _findall(root, './/t:LinSection/t:Lin')
        assert len(lins) == 2

    def test_totals_correct(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=0, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))

        from gov.teif.builder import build_unsigned_teif
        xml_bytes = build_unsigned_teif(invoice, seller)
        root = etree.fromstring(xml_bytes)

        # Find all Moa elements and check by amountTypeCode
        moas = root.findall('.//InvoiceMoa//Moa')
        moa_map = {m.get('amountTypeCode'): m.find('Amount').text for m in moas}

        assert 'I-172' in moa_map  # Total HT
        assert 'I-176' in moa_map  # Total HT after discount
        assert 'I-181' in moa_map  # TVA
        assert 'I-180' in moa_map  # Total TTC

    def test_discount_section_present_when_discount(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=10, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))

        from gov.teif.builder import build_unsigned_teif
        xml_bytes = build_unsigned_teif(invoice, seller)
        root = etree.fromstring(xml_bytes)

        alc = _find(root, './/t:InvoiceAlc')
        assert alc is not None

    def test_discount_section_absent_when_no_discount(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=0, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))

        from gov.teif.builder import build_unsigned_teif
        xml_bytes = build_unsigned_teif(invoice, seller)
        root = etree.fromstring(xml_bytes)

        alc = _find(root, './/t:InvoiceAlc')
        assert alc is None

    def test_raises_valueerror_no_client(self, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory(client=None)

        from gov.teif.builder import build_unsigned_teif
        with pytest.raises(ValueError, match='client'):
            build_unsigned_teif(invoice, seller)

    def test_raises_valueerror_no_unique_id(self, tenant, seller):
        from tests.factories import InvoiceFactory, ClientFactory
        # Create invoice normally, then wipe uniqueId in-memory (save() auto-generates it)
        invoice = InvoiceFactory()
        invoice.uniqueId = ''

        from gov.teif.builder import build_unsigned_teif
        with pytest.raises(ValueError, match='uniqueId'):
            build_unsigned_teif(invoice, seller)

    def test_raises_valueerror_no_mf(self, tenant, seller):
        from tests.factories import InvoiceFactory, ClientFactory
        client = ClientFactory(mf='')
        invoice = InvoiceFactory(client=client)

        from gov.teif.builder import build_unsigned_teif
        with pytest.raises(ValueError, match='MF'):
            build_unsigned_teif(invoice, seller)


@pytest.mark.django_db(transaction=True)
class TestBuildUnsignedTeifAvoir:
    def test_bgm_doc_type_avoir(self, tenant, seller):
        from tests.factories import CreditNoteFactory

        from gov.teif.builder import build_unsigned_teif_avoir
        cn = CreditNoteFactory(amount_ht=Decimal('500.000'))
        xml_bytes = build_unsigned_teif_avoir(cn, seller)
        root = etree.fromstring(xml_bytes)

        doc_type = _find(root, './/t:DocumentType')
        assert doc_type.get('code') == 'I-12'
        assert doc_type.text == 'Avoir'

    def test_has_single_line_item(self, tenant, seller):
        from tests.factories import CreditNoteFactory

        from gov.teif.builder import build_unsigned_teif_avoir
        cn = CreditNoteFactory(amount_ht=Decimal('500.000'))
        xml_bytes = build_unsigned_teif_avoir(cn, seller)
        root = etree.fromstring(xml_bytes)

        lins = _findall(root, './/t:LinSection/t:Lin')
        assert len(lins) == 1

    def test_avoir_totals_no_timbre(self, tenant, seller):
        from tests.factories import CreditNoteFactory

        from gov.teif.builder import build_unsigned_teif_avoir
        cn = CreditNoteFactory(amount_ht=Decimal('500.000'))
        xml_bytes = build_unsigned_teif_avoir(cn, seller)
        root = etree.fromstring(xml_bytes)

        moas = root.findall('.//InvoiceMoa//Moa')
        timbre = [m for m in moas if m.get('amountTypeCode') == 'I-179']
        assert len(timbre) == 1
        assert timbre[0].find('Amount').text == '0.000'

    def test_raises_valueerror_no_client(self, tenant, seller):
        from unittest.mock import PropertyMock, patch
        from tests.factories import CreditNoteFactory
        # CreditNote.client is a non-nullable FK so we patch it to return None
        cn = CreditNoteFactory.build()
        with patch.object(type(cn), 'client', new_callable=PropertyMock, return_value=None):
            from gov.teif.builder import build_unsigned_teif_avoir
            with pytest.raises(ValueError, match='client'):
                build_unsigned_teif_avoir(cn, seller)

    def test_raises_valueerror_no_unique_id(self, tenant, seller):
        from tests.factories import CreditNoteFactory
        # Create credit note normally, then wipe uniqueId in-memory (save() auto-generates it)
        cn = CreditNoteFactory()
        cn.uniqueId = ''

        from gov.teif.builder import build_unsigned_teif_avoir
        with pytest.raises(ValueError, match='uniqueId'):
            build_unsigned_teif_avoir(cn, seller)

    def test_raises_valueerror_no_mf(self, tenant, seller):
        from tests.factories import CreditNoteFactory, ClientFactory
        client = ClientFactory(mf='')
        cn = CreditNoteFactory(client=client)

        from gov.teif.builder import build_unsigned_teif_avoir
        with pytest.raises(ValueError, match='MF'):
            build_unsigned_teif_avoir(cn, seller)


class TestSanitize:
    def test_strips_forbidden_chars(self):
        from gov.teif.builder import _sanitize
        assert _sanitize('hello%world/test\\foo<bar>baz&"qux\'end') == 'helloworldtestfoobarbazquxend'

    def test_returns_empty_unchanged(self):
        from gov.teif.builder import _sanitize
        assert _sanitize('') == ''
        assert _sanitize(None) is None


class TestCondenseToSingleLine:
    def test_removes_whitespace_between_tags(self):
        from gov.teif.builder import condense_to_single_line
        xml = b'<?xml version="1.0"?>\n<root>\n  <child>text</child>\n</root>'
        result = condense_to_single_line(xml)
        assert b'\n' not in result
        assert b'>  <' not in result
        assert b'<child>text</child>' in result
