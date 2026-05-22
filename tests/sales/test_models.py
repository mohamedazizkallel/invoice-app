import pytest
from decimal import Decimal
from unittest.mock import patch


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

    def test_quantity_multiplies_line_total(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=0, tva=0, timbre_fiscal=0)
        line = InvoiceServiceFactory(
            invoice=invoice, unit_price=Decimal('100.000'), quantity=Decimal('3'),
        )
        assert line.get_line_ht() == Decimal('300.000')
        assert invoice.calculate_service_subtotal() == Decimal('300.000')

    def test_quantity_defaults_to_one(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(discount=0, tva=0, timbre_fiscal=0)
        line = InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        assert line.quantity == Decimal('1')
        assert line.get_line_ht() == Decimal('100.000')

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
class TestSettingsGetCached:
    def test_returns_settings_instance(self, tenant, seller):
        from sales.models import Settings
        result = Settings.get_cached()
        assert result is not None
        assert result.pk == seller.pk

    def test_returns_none_when_no_settings(self, tenant):
        from sales.models import Settings
        from django.core.cache import cache
        cache.clear()
        Settings.objects.all().delete()
        result = Settings.get_cached()
        assert result is None

    def test_invalidates_on_save(self, tenant, seller):
        from sales.models import Settings
        from django.core.cache import cache
        # Prime the cache
        Settings.get_cached()
        # Change and save
        with patch('sales.models._sync_ngsign_org'):
            seller.clientname = 'Updated Name'
            seller.save()
        # Cache should return updated instance
        result = Settings.get_cached()
        assert result.clientname == 'Updated Name'


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


@pytest.mark.django_db(transaction=True)
class TestClientModel:
    def test_save_generates_unique_id_and_slug(self, tenant, seller):
        from tests.factories import ClientFactory
        client = ClientFactory(uniqueId=None, slug=None)
        assert client.uniqueId is not None
        assert client.slug is not None

    def test_get_balance_net_debit(self, tenant, seller):
        from tests.factories import ClientFactory, ClientTransactionFactory
        client = ClientFactory()
        ClientTransactionFactory(client=client, transaction_type='DEBIT', amount=Decimal('500.000'))
        ClientTransactionFactory(client=client, transaction_type='CREDIT', amount=Decimal('200.000'))
        assert client.get_balance() == Decimal('300.000')

    def test_get_balance_no_transactions(self, tenant, seller):
        from tests.factories import ClientFactory
        client = ClientFactory()
        assert client.get_balance() == Decimal('0')

    def test_mf_cache_invalidation(self, tenant, seller):
        from tests.factories import ClientFactory
        from django.core.cache import cache
        from sales.models import Client as ClientModel
        client = ClientFactory(mf='TEST123')
        mf_map = ClientModel.get_mf_map()
        assert 'test123' in mf_map
        client.delete()
        mf_map = ClientModel.get_mf_map()
        assert 'test123' not in mf_map


@pytest.mark.django_db(transaction=True)
class TestSupplierModel:
    def test_save_generates_unique_id_and_slug(self, tenant, seller):
        from tests.factories import SupplierFactory
        supplier = SupplierFactory(uniqueId=None, slug=None)
        assert supplier.uniqueId is not None
        assert supplier.slug is not None

    def test_get_balance_net_credit(self, tenant, seller):
        from tests.factories import SupplierFactory, SupplierTransactionFactory
        supplier = SupplierFactory()
        SupplierTransactionFactory(supplier=supplier, transaction_type='CREDIT', amount=Decimal('500.000'))
        SupplierTransactionFactory(supplier=supplier, transaction_type='DEBIT', amount=Decimal('200.000'))
        assert supplier.get_balance() == Decimal('300.000')

    def test_mf_cache_invalidation(self, tenant, seller):
        from tests.factories import SupplierFactory
        from django.core.cache import cache
        from sales.models import Supplier as SupplierModel
        supplier = SupplierFactory(mf='SUPP123')
        mf_map = SupplierModel.get_mf_map()
        assert 'supp123' in mf_map
        supplier.delete()
        mf_map = SupplierModel.get_mf_map()
        assert 'supp123' not in mf_map


@pytest.mark.django_db(transaction=True)
class TestSupplyModel:
    def test_is_low_stock_true(self, tenant, seller):
        from tests.factories import SupplyFactory
        supply = SupplyFactory(stock_quantity=Decimal('5.000'), min_stock=Decimal('10.000'))
        assert supply.is_low_stock is True

    def test_is_low_stock_false(self, tenant, seller):
        from tests.factories import SupplyFactory
        supply = SupplyFactory(stock_quantity=Decimal('50.000'), min_stock=Decimal('10.000'))
        assert supply.is_low_stock is False


@pytest.mark.django_db(transaction=True)
class TestPurchaseModel:
    def test_calculate_subtotal(self, tenant, seller):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory()
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('2.000'), unit_price=Decimal('50.000'))
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('3.000'), unit_price=Decimal('30.000'))
        assert purchase.calculate_subtotal() == Decimal('190.000')

    def test_calculate_discount_amount(self, tenant, seller):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory(discount=Decimal('10.00'))
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('1000.000'))
        assert purchase.calculate_discount_amount() == Decimal('100.000')

    def test_calculate_total_fodec(self, tenant, seller):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory()
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('1000.000'), has_fodec=True)
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('500.000'), has_fodec=False)
        assert purchase.calculate_total_fodec() == Decimal('1000.000') * Decimal('0.01')

    def test_calculate_tva_amount(self, tenant, seller):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory(tva=Decimal('19.00'), discount=Decimal('0.00'))
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('1000.000'))
        assert purchase.calculate_tva_amount() == Decimal('190.000')

    def test_calculate_total(self, tenant, seller):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory(tva=Decimal('19.00'), discount=Decimal('0.00'), timbre_fiscal=Decimal('1.000'))
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('1000.000'))
        assert purchase.calculate_total() == Decimal('1191.000')

    def test_get_net_amount(self, tenant, seller):
        from tests.factories import PurchaseFactory, PurchaseLineFactory, PurchaseRetenuFactory
        purchase = PurchaseFactory(tva=Decimal('19.00'), timbre_fiscal=Decimal('1.000'))
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('1000.000'))
        total = purchase.calculate_total()
        PurchaseRetenuFactory(purchase=purchase, base_amount=total, retenu_rate=Decimal('1.00'))
        net = purchase.get_net_amount()
        assert net == total - purchase.get_total_retenue()

    def test_uniqueId_sequential(self, tenant, seller):
        from sales.models import Purchase
        from tests.factories import PurchaseFactory
        p1 = PurchaseFactory(uniqueId=None, slug=None)
        p2 = PurchaseFactory(uniqueId=None, slug=None)
        assert p1.uniqueId.startswith('001-')
        assert p2.uniqueId.startswith('002-')


@pytest.mark.django_db(transaction=True)
class TestPurchaseLineModel:
    def test_get_line_total(self, tenant, seller):
        from tests.factories import PurchaseLineFactory
        line = PurchaseLineFactory(quantity=Decimal('3.000'), unit_price=Decimal('25.000'))
        assert line.get_line_total() == Decimal('75.000')

    def test_get_fodec_amount(self, tenant, seller):
        from tests.factories import PurchaseLineFactory
        line_with = PurchaseLineFactory(quantity=Decimal('1.000'), unit_price=Decimal('1000.000'), has_fodec=True)
        line_without = PurchaseLineFactory(quantity=Decimal('1.000'), unit_price=Decimal('1000.000'), has_fodec=False)
        assert line_with.get_fodec_amount() == Decimal('10.000')
        assert line_without.get_fodec_amount() == Decimal('0')


@pytest.mark.django_db(transaction=True)
class TestInvoiceModelExpanded:
    """Additional invoice model tests beyond TestInvoiceCalculations."""

    def test_calculate_total_fodec(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory, ServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0)
        svc = ServiceFactory(apply_fodec=True)
        InvoiceServiceFactory(invoice=invoice, service=svc, unit_price=Decimal('1000.000'), has_fodec=True)
        assert invoice.calculate_total_fodec() == Decimal('10.000')

    def test_calculate_total_tva(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))
        total_tva = invoice.calculate_total_tva()
        total = invoice.calculate_total()
        assert total_tva == total - invoice.get_timbre_fiscal()

    def test_get_total_retenue(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory, InvoiceRetenuFactory
        invoice = InvoiceFactory(tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))
        InvoiceRetenuFactory(invoice=invoice, base_amount=Decimal('1000.000'), retenu_rate=Decimal('1.00'))
        assert invoice.get_total_retenue() == Decimal('10.000')

    def test_get_net_amount(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory, InvoiceRetenuFactory
        invoice = InvoiceFactory(tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))
        InvoiceRetenuFactory(invoice=invoice, base_amount=Decimal('1000.000'), retenu_rate=Decimal('1.00'))
        total = invoice.calculate_total()
        assert invoice.get_net_amount() == total - Decimal('10.000')

    def test_get_auto_retenu_above_threshold(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        from unittest.mock import patch
        with patch('sales.models._sync_ngsign_org'):
            from sales.models import Settings
            s = Settings.get_cached() or seller
            s.default_retenu_rate = Decimal('1.00')
            s.save()
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('5000.000'))
        auto = invoice.get_auto_retenu_amount()
        assert auto > Decimal('0')

    def test_get_auto_retenu_below_threshold(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        from unittest.mock import patch
        with patch('sales.models._sync_ngsign_org'):
            from sales.models import Settings
            s = Settings.get_cached() or seller
            s.default_retenu_rate = Decimal('1.00')
            s.save()
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        assert invoice.get_auto_retenu_amount() == Decimal('0')

    def test_get_auto_retenu_manual_exists(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory, InvoiceRetenuFactory
        from unittest.mock import patch
        with patch('sales.models._sync_ngsign_org'):
            from sales.models import Settings
            s = Settings.get_cached() or seller
            s.default_retenu_rate = Decimal('1.00')
            s.save()
        invoice = InvoiceFactory(tva=19)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('5000.000'))
        InvoiceRetenuFactory(invoice=invoice, base_amount=Decimal('1000.000'))
        assert invoice.get_auto_retenu_amount() == Decimal('0')

    def test_get_credit_notes_total(self, tenant, seller):
        from tests.factories import InvoiceFactory, CreditNoteFactory
        invoice = InvoiceFactory()
        CreditNoteFactory(client=invoice.client, invoice=invoice, amount_ht=Decimal('100.000'), tva=19)
        CreditNoteFactory(client=invoice.client, invoice=invoice, amount_ht=Decimal('200.000'), tva=19)
        total = invoice.get_credit_notes_total()
        assert total == Decimal('119.000') + Decimal('238.000')

    def test_has_retenue(self, tenant, seller):
        from tests.factories import InvoiceFactory, InvoiceRetenuFactory
        invoice = InvoiceFactory()
        assert invoice.has_retenue() is False
        InvoiceRetenuFactory(invoice=invoice)
        assert invoice.has_retenue() is True

    def test_uniqueId_sequential(self, tenant, seller):
        from tests.factories import InvoiceFactory
        i1 = InvoiceFactory(uniqueId=None, slug=None)
        i2 = InvoiceFactory(uniqueId=None, slug=None)
        assert i1.uniqueId.startswith('FV-')
        assert i2.uniqueId.startswith('FV-')
        n1 = int(i1.uniqueId.split('-')[1])
        n2 = int(i2.uniqueId.split('-')[1])
        assert n2 == n1 + 1

    def test_save_auto_populates_from_settings(self, tenant, seller):
        from sales.models import Invoice
        from unittest.mock import patch
        with patch('sales.models._sync_ngsign_org'):
            seller.tva = Decimal('7.00')
            seller.dt = Decimal('0.600')
            seller.save()
        invoice = Invoice.objects.create(
            client=None, tva=None, timbre_fiscal=None
        )
        assert invoice.tva == Decimal('7.00')
        assert invoice.timbre_fiscal == Decimal('0.600')


@pytest.mark.django_db(transaction=True)
class TestInvoiceServiceModel:
    def test_get_line_ht_flat(self, tenant, seller):
        from tests.factories import InvoiceServiceFactory, ServiceFactory
        svc = ServiceFactory(billing_type='flat')
        line = InvoiceServiceFactory(service=svc, unit_price=Decimal('500.000'))
        assert line.get_line_ht() == Decimal('500.000')

    def test_get_line_ht_hour(self, tenant, seller):
        from tests.factories import InvoiceServiceFactory, ServiceFactory
        svc = ServiceFactory(billing_type='hour')
        line = InvoiceServiceFactory(service=svc, unit_price=Decimal('50.000'), hours_used=8)
        assert line.get_line_ht() == Decimal('400.000')

    def test_get_line_ht_day(self, tenant, seller):
        from tests.factories import InvoiceServiceFactory, ServiceFactory
        svc = ServiceFactory(billing_type='day')
        line = InvoiceServiceFactory(service=svc, unit_price=Decimal('200.000'), days_used=5)
        assert line.get_line_ht() == Decimal('1000.000')

    def test_get_line_ht_unit(self, tenant, seller):
        from tests.factories import InvoiceServiceFactory, ServiceFactory
        svc = ServiceFactory(billing_type='unit')
        line = InvoiceServiceFactory(service=svc, unit_price=Decimal('15.000'), units_used=10)
        assert line.get_line_ht() == Decimal('150.000')


@pytest.mark.django_db(transaction=True)
class TestCreditNoteModel:
    def test_uniqueId_sequential(self, tenant, seller):
        from tests.factories import CreditNoteFactory
        cn1 = CreditNoteFactory(uniqueId=None, slug=None)
        cn2 = CreditNoteFactory(uniqueId=None, slug=None)
        assert cn1.uniqueId.startswith('AV-')
        assert cn2.uniqueId.startswith('AV-')


@pytest.mark.django_db(transaction=True)
class TestSettingsModel:
    def test_save_auto_generates_fields(self, tenant):
        from sales.models import Settings
        from unittest.mock import patch
        with patch('sales.models._sync_ngsign_org'):
            s = Settings.objects.create(clientname='Test Co')
        assert s.uniqueId is not None
        assert s.slug is not None
        assert s.date_created is not None


@pytest.mark.django_db(transaction=True)
class TestBonLivraisonModel:
    def test_calculate_total_ht(self, tenant, seller):
        from tests.factories import BonLivraisonFactory, BonLivraisonLineFactory
        bon = BonLivraisonFactory()
        BonLivraisonLineFactory(bon=bon, amount=Decimal('100.000'))
        BonLivraisonLineFactory(bon=bon, amount=Decimal('200.000'))
        assert bon.calculate_total_ht() == Decimal('300.000')

    def test_calculate_tva_amount(self, tenant, seller):
        from tests.factories import BonLivraisonFactory, BonLivraisonLineFactory
        bon = BonLivraisonFactory(tva=Decimal('19.00'))
        BonLivraisonLineFactory(bon=bon, amount=Decimal('1000.000'))
        assert bon.calculate_tva_amount() == Decimal('190.000')

    def test_calculate_total_ttc(self, tenant, seller):
        from tests.factories import BonLivraisonFactory, BonLivraisonLineFactory
        bon = BonLivraisonFactory(tva=Decimal('19.00'))
        BonLivraisonLineFactory(bon=bon, amount=Decimal('1000.000'))
        assert bon.calculate_total_ttc() == Decimal('1190.000')

    def test_uniqueId_sequential(self, tenant, seller):
        from tests.factories import BonLivraisonFactory
        b1 = BonLivraisonFactory(uniqueId=None, slug=None)
        b2 = BonLivraisonFactory(uniqueId=None, slug=None)
        assert b1.uniqueId.startswith('BL-')
        assert b2.uniqueId.startswith('BL-')


@pytest.mark.django_db(transaction=True)
class TestDevisModel:
    def test_calculate_service_subtotal(self, tenant, seller):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory()
        DevisServiceFactory(devis=devis, unit_price=Decimal('100.000'))
        DevisServiceFactory(devis=devis, unit_price=Decimal('200.000'))
        assert devis.calculate_service_subtotal() == Decimal('300.000')

    def test_calculate_total_fodec(self, tenant, seller):
        from tests.factories import DevisFactory, DevisServiceFactory, ServiceFactory
        devis = DevisFactory()
        svc = ServiceFactory(apply_fodec=True)
        DevisServiceFactory(devis=devis, service=svc, unit_price=Decimal('1000.000'), has_fodec=True)
        assert devis.calculate_total_fodec() == Decimal('10.000')

    def test_calculate_discount_amount(self, tenant, seller):
        from tests.factories import DevisFactory, DevisServiceFactory, ServiceFactory
        devis = DevisFactory(discount=Decimal('10.00'))
        svc = ServiceFactory(apply_fodec=True)
        DevisServiceFactory(devis=devis, service=svc, unit_price=Decimal('1000.000'), has_fodec=True)
        expected = (Decimal('1000.000') + Decimal('10.000')) * Decimal('10.00') / Decimal('100')
        assert devis.calculate_discount_amount() == expected

    def test_calculate_tva_amount(self, tenant, seller):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory(tva=Decimal('19.00'), discount=Decimal('0.00'))
        DevisServiceFactory(devis=devis, unit_price=Decimal('1000.000'))
        assert devis.calculate_tva_amount() == Decimal('190.000')

    def test_calculate_total(self, tenant, seller):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory(tva=Decimal('19.00'), timbre_fiscal=Decimal('1.000'), discount=Decimal('0.00'))
        DevisServiceFactory(devis=devis, unit_price=Decimal('1000.000'))
        assert devis.calculate_total() == Decimal('1191.000')

    def test_convert_to_invoice(self, tenant, seller):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory(tva=Decimal('19.00'))
        DevisServiceFactory(devis=devis, unit_price=Decimal('100.000'))
        DevisServiceFactory(devis=devis, unit_price=Decimal('200.000'))
        invoice = devis.convert_to_invoice()
        assert invoice is not None
        assert invoice.client == devis.client
        assert invoice.invoice_services.count() == 2
        devis.refresh_from_db()
        assert devis.status == 'ACCEPTED'
        assert devis.converted_invoice == invoice

    def test_convert_idempotent(self, tenant, seller):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory()
        DevisServiceFactory(devis=devis)
        invoice1 = devis.convert_to_invoice()
        invoice2 = devis.convert_to_invoice()
        assert invoice1.pk == invoice2.pk

    def test_uniqueId_sequential(self, tenant, seller):
        from tests.factories import DevisFactory
        d1 = DevisFactory(uniqueId=None, slug=None)
        d2 = DevisFactory(uniqueId=None, slug=None)
        assert d1.uniqueId.startswith('DV-')
        assert d2.uniqueId.startswith('DV-')


@pytest.mark.django_db(transaction=True)
class TestInvoiceGenerateUniqueId:
    def test_auto_starts_at_one(self, tenant, seller):
        from sales.models import Invoice
        assert Invoice.generate_unique_id(2026) == 'FV-001-2026'

    def test_auto_increments_from_max(self, tenant, seller):
        from sales.models import Invoice
        from tests.factories import InvoiceFactory
        InvoiceFactory(uniqueId='FV-005-2026')
        InvoiceFactory(uniqueId='FV-003-2026')
        assert Invoice.generate_unique_id(2026) == 'FV-006-2026'

    def test_auto_is_per_year(self, tenant, seller):
        from sales.models import Invoice
        from tests.factories import InvoiceFactory
        InvoiceFactory(uniqueId='FV-010-2025')
        assert Invoice.generate_unique_id(2026) == 'FV-001-2026'

    def test_manual_number_formats(self, tenant, seller):
        from sales.models import Invoice
        assert Invoice.generate_unique_id(2026, manual_number=42) == 'FV-042-2026'

    def test_manual_number_collision_raises(self, tenant, seller):
        from sales.models import Invoice
        from tests.factories import InvoiceFactory
        InvoiceFactory(uniqueId='FV-007-2026')
        with pytest.raises(ValueError, match='FV-007-2026'):
            Invoice.generate_unique_id(2026, manual_number=7)

    def test_manual_number_out_of_range_raises(self, tenant, seller):
        from sales.models import Invoice
        with pytest.raises(ValueError):
            Invoice.generate_unique_id(2026, manual_number=0)
        with pytest.raises(ValueError):
            Invoice.generate_unique_id(2026, manual_number=1000)

    def test_manual_number_excludes_self(self, tenant, seller):
        from sales.models import Invoice
        from tests.factories import InvoiceFactory
        inv = InvoiceFactory(uniqueId='FV-009-2026')
        assert Invoice.generate_unique_id(2026, manual_number=9, exclude_pk=inv.pk) == 'FV-009-2026'


@pytest.mark.django_db(transaction=True)
class TestCreditNoteGenerateUniqueId:
    def test_auto_starts_at_one(self, tenant, seller):
        from sales.models import CreditNote
        assert CreditNote.generate_unique_id(2026) == 'AV-001-2026'

    def test_auto_increments_from_max(self, tenant, seller):
        from sales.models import CreditNote
        from tests.factories import CreditNoteFactory
        CreditNoteFactory(uniqueId='AV-005-2026')
        CreditNoteFactory(uniqueId='AV-003-2026')
        assert CreditNote.generate_unique_id(2026) == 'AV-006-2026'

    def test_manual_number_formats(self, tenant, seller):
        from sales.models import CreditNote
        assert CreditNote.generate_unique_id(2026, manual_number=42) == 'AV-042-2026'

    def test_manual_number_collision_raises(self, tenant, seller):
        from sales.models import CreditNote
        from tests.factories import CreditNoteFactory
        CreditNoteFactory(uniqueId='AV-007-2026')
        with pytest.raises(ValueError, match='AV-007-2026'):
            CreditNote.generate_unique_id(2026, manual_number=7)

    def test_manual_number_out_of_range_raises(self, tenant, seller):
        from sales.models import CreditNote
        with pytest.raises(ValueError):
            CreditNote.generate_unique_id(2026, manual_number=0)
        with pytest.raises(ValueError):
            CreditNote.generate_unique_id(2026, manual_number=1000)

    def test_manual_number_excludes_self(self, tenant, seller):
        from sales.models import CreditNote
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory(uniqueId='AV-009-2026')
        assert CreditNote.generate_unique_id(2026, manual_number=9, exclude_pk=cn.pk) == 'AV-009-2026'


@pytest.mark.django_db(transaction=True)
class TestServiceModel:
    def test_total_price_flat(self, tenant, seller):
        from tests.factories import ServiceFactory
        svc = ServiceFactory(billing_type='flat', price=Decimal('500.000'))
        assert svc.total_price == Decimal('500.000')

    def test_total_price_day(self, tenant, seller):
        from tests.factories import ServiceFactory
        svc = ServiceFactory(billing_type='day', price=Decimal('200.000'), duration_days=5)
        assert svc.total_price == Decimal('1000.000')

    def test_total_price_hour(self, tenant, seller):
        from tests.factories import ServiceFactory
        svc = ServiceFactory(billing_type='hour', price=Decimal('50.000'), duration_hours=8)
        assert svc.total_price == Decimal('400.000')

    def test_total_price_unit(self, tenant, seller):
        from tests.factories import ServiceFactory
        svc = ServiceFactory(billing_type='unit', price=Decimal('25.000'))
        assert svc.total_price == Decimal('25.000')
