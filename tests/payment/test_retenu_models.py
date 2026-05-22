import pytest
from decimal import Decimal


@pytest.mark.django_db(transaction=True)
class TestInvoiceRetenuModel:
    def test_auto_calculates_amount(self, tenant, seller):
        from tests.factories import InvoiceRetenuFactory
        retenu = InvoiceRetenuFactory(
            base_amount=Decimal('5000.000'),
            retenu_rate=Decimal('1.50'),
        )
        assert retenu.retenu_amount == Decimal('75.000')

    def test_auto_populates_rate(self, tenant, seller):
        from tests.factories import InvoiceFactory, RetenuFactory
        from payment.models import InvoiceRetenu
        invoice = InvoiceFactory()
        retenu_type = RetenuFactory(rate=Decimal('2.50'))
        ir = InvoiceRetenu(
            invoice=invoice,
            retenu_type=retenu_type,
            base_amount=Decimal('1000.000'),
        )
        ir.save()
        assert ir.retenu_rate == Decimal('2.50')
        assert ir.retenu_amount == Decimal('25.000')

    def test_calculate_amount_method(self, tenant, seller):
        from tests.factories import InvoiceRetenuFactory
        retenu = InvoiceRetenuFactory(
            base_amount=Decimal('2000.000'),
            retenu_rate=Decimal('5.00'),
        )
        assert retenu.calculate_amount() == Decimal('100.000')


@pytest.mark.django_db(transaction=True)
class TestPurchaseRetenuModel:
    def test_auto_calculates(self, tenant, seller):
        from tests.factories import PurchaseRetenuFactory
        retenu = PurchaseRetenuFactory(
            base_amount=Decimal('3000.000'),
            retenu_rate=Decimal('2.00'),
        )
        assert retenu.retenu_amount == Decimal('60.000')

    def test_auto_populates_rate(self, tenant, seller):
        from tests.factories import PurchaseFactory, RetenuFactory
        from payment.models import PurchaseRetenu
        purchase = PurchaseFactory()
        retenu_type = RetenuFactory(rate=Decimal('1.50'))
        pr = PurchaseRetenu(
            purchase=purchase,
            retenu_type=retenu_type,
            base_amount=Decimal('1000.000'),
        )
        pr.save()
        assert pr.retenu_rate == Decimal('1.50')
        assert pr.retenu_amount == Decimal('15.000')


@pytest.mark.django_db(transaction=True)
class TestRetenuStr:
    def test_str_display(self, tenant, seller):
        from tests.factories import RetenuFactory
        retenu = RetenuFactory(
            category='LOYERS',
            subcategory='LOYER_HOTEL',
            rate=Decimal('10.00'),
        )
        display = str(retenu)
        assert "Loyers d'hôtels" in display
