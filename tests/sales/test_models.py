import pytest
from decimal import Decimal


@pytest.mark.django_db(transaction=True)
class TestInvoiceCalculations:
    def test_calculate_service_subtotal(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=0, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('200.000'))

        assert invoice.calculate_service_subtotal() == Decimal('300.000')

    def test_calculate_discount_amount(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=10, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))

        assert invoice.calculate_discount_amount() == Decimal('100.000')

    def test_calculate_discount_zero(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=0, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))

        assert invoice.calculate_discount_amount() == Decimal('0')

    def test_calculate_subtotal_after_discount(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=10, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))

        assert invoice.calculate_subtotal_after_discount() == Decimal('900.000')

    def test_calculate_tva_amount(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=0, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))

        expected_tva = Decimal('1000.000') * Decimal('19') / Decimal('100')
        assert invoice.calculate_tva_amount() == expected_tva

    def test_calculate_total(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=0, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))

        total = invoice.calculate_total()
        subtotal = invoice.calculate_subtotal_after_discount()
        tva = invoice.calculate_tva_amount()
        timbre = invoice.get_timbre_fiscal()
        assert total == subtotal + tva + timbre

    def test_get_tva(self, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory(tva=19)
        assert invoice.get_tva() == 19

    def test_get_timbre_fiscal(self, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()
        timbre = invoice.get_timbre_fiscal()
        assert timbre >= Decimal('0')

    def test_100_percent_discount(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=100, tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))

        assert invoice.calculate_subtotal_after_discount() == Decimal('0')
        assert invoice.calculate_tva_amount() == Decimal('0')

    def test_no_services_returns_zero(self, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        assert invoice.calculate_service_subtotal() == Decimal('0')


@pytest.mark.django_db(transaction=True)
class TestCreditNoteCalculations:
    def test_calculate_tva_amount(self, tenant, seller):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory(amount_ht=Decimal('1000.000'), tva=19)

        expected = Decimal('1000.000') * Decimal('19') / Decimal('100')
        assert cn.calculate_tva_amount() == expected

    def test_calculate_total(self, tenant, seller):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory(amount_ht=Decimal('1000.000'), tva=19)

        total = cn.calculate_total()
        assert total == Decimal('1000.000') + cn.calculate_tva_amount()
