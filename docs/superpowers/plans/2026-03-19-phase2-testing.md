# Phase 2 Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add comprehensive test coverage for the sales app, payment system, and utilities — everything outside NGSign.

**Architecture:** Extend the existing pytest + pytest-django + factory-boy infrastructure from Phase 1. Tests are organized into `tests/sales/` and `tests/payment/` subdirectories. All tests use real PostgreSQL via the existing tenant fixture.

**Tech Stack:** pytest, pytest-django, factory-boy, pytest-cov

**Spec:** `docs/superpowers/specs/2026-03-19-phase2-testing-design.md`

---

### Task 1: Add Phase 2 Factories

**Files:**
- Modify: `tests/factories.py`

- [ ] **Step 1: Add new factories to factories.py**

Append these factories after the existing `NGSignClientAccountFactory`:

Ensure `from decimal import Decimal` is at the top of `factories.py` (add it if not already present).

```python
# ── Phase 2 factories ────────────────────────────────────────
from decimal import Decimal  # add to top-level imports if missing

class SupplierFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Supplier'

    name = factory.Sequence(lambda n: f'Supplier {n}')
    mf = factory.Sequence(lambda n: f'MF-S-{n:04d}')
    adress = '123 Supplier St'
    status = 'PM'


class SupplyFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Supply'

    name = factory.Sequence(lambda n: f'Supply {n}')
    category = 'raw_material'
    unit = 'pièce'
    unit_price = factory.LazyFunction(lambda: Decimal('10.000'))
    stock_quantity = factory.LazyFunction(lambda: Decimal('100.000'))
    min_stock = factory.LazyFunction(lambda: Decimal('10.000'))
    apply_fodec = False


class PurchaseFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Purchase'

    supplier = factory.SubFactory(SupplierFactory)
    status = 'DRAFT'
    tva = factory.LazyFunction(lambda: Decimal('19.00'))
    discount = factory.LazyFunction(lambda: Decimal('0.00'))
    timbre_fiscal = factory.LazyFunction(lambda: Decimal('1.000'))


class PurchaseLineFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.PurchaseLine'

    purchase = factory.SubFactory(PurchaseFactory)
    supply = factory.SubFactory(SupplyFactory)
    quantity = factory.LazyFunction(lambda: Decimal('5.000'))
    unit_price = factory.LazyFunction(lambda: Decimal('10.000'))
    has_fodec = False


class ClientTransactionFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.ClientTransaction'

    client = factory.SubFactory(ClientFactory)
    transaction_type = 'DEBIT'
    source = 'MANUAL'
    amount = factory.LazyFunction(lambda: Decimal('100.000'))


class SupplierTransactionFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.SupplierTransaction'

    supplier = factory.SubFactory(SupplierFactory)
    transaction_type = 'CREDIT'
    source = 'MANUAL'
    amount = factory.LazyFunction(lambda: Decimal('100.000'))


class DevisFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Devis'

    client = factory.SubFactory(ClientFactory)
    title = factory.Sequence(lambda n: f'Devis {n}')
    tva = factory.LazyFunction(lambda: Decimal('19.00'))
    timbre_fiscal = factory.LazyFunction(lambda: Decimal('1.000'))
    discount = factory.LazyFunction(lambda: Decimal('0.00'))
    status = 'PENDING'


class DevisServiceFactory(DjangoModelFactory):
    """InvoiceService linked to a Devis (not an Invoice)."""
    class Meta:
        model = 'sales.InvoiceService'

    devis = factory.SubFactory(DevisFactory)
    invoice = None
    service = factory.SubFactory(ServiceFactory)
    unit_price = factory.LazyFunction(lambda: Decimal('100.000'))
    has_fodec = False


class BonLivraisonFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.BonLivraison'

    client = factory.SubFactory(ClientFactory)
    status = 'DRAFT'
    tva = factory.LazyFunction(lambda: Decimal('19.00'))


class BonLivraisonLineFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.BonLivraisonLine'

    bon = factory.SubFactory(BonLivraisonFactory)
    description = factory.Sequence(lambda n: f'Line item {n}')
    amount = factory.LazyFunction(lambda: Decimal('50.000'))


class RetenuFactory(DjangoModelFactory):
    class Meta:
        model = 'payment.Retenu'

    category = 'ACQUISITIONS'
    subcategory = factory.Sequence(lambda n: f'ACQ_TEST_{n}')
    rate = factory.LazyFunction(lambda: Decimal('1.00'))
    is_active = True


class InvoiceRetenuFactory(DjangoModelFactory):
    class Meta:
        model = 'payment.InvoiceRetenu'

    invoice = factory.SubFactory(InvoiceFactory)
    retenu_type = factory.SubFactory(RetenuFactory)
    base_amount = factory.LazyFunction(lambda: Decimal('1000.000'))
    retenu_rate = factory.LazyAttribute(lambda o: o.retenu_type.rate)
    retenu_amount = factory.LazyAttribute(
        lambda o: (o.base_amount * o.retenu_rate) / Decimal('100')
    )


class PurchaseRetenuFactory(DjangoModelFactory):
    class Meta:
        model = 'payment.PurchaseRetenu'

    purchase = factory.SubFactory(PurchaseFactory)
    retenu_type = factory.SubFactory(RetenuFactory)
    base_amount = factory.LazyFunction(lambda: Decimal('1000.000'))
    retenu_rate = factory.LazyAttribute(lambda o: o.retenu_type.rate)
    retenu_amount = factory.LazyAttribute(
        lambda o: (o.base_amount * o.retenu_rate) / Decimal('100')
    )
```

Note: The `Decimal` import already exists at the top of `factories.py` via the existing `LazyFunction` lambdas. Add `from decimal import Decimal` at the top if not already present.

- [ ] **Step 2: Verify factories compile**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_models.py -v --co`
Expected: existing tests collected without import errors

- [ ] **Step 3: Commit**

```bash
git add tests/factories.py
git commit -m "feat: add Phase 2 factories for sales, payment, and devis models"
```

---

### Task 2: Add Cache-Clearing Fixture to Conftest

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add autouse clear_cache fixture**

Add after the existing `ngsign_account` fixture:

```python
@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before and after each test."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_models.py -v`
Expected: all existing model tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: add autouse cache-clearing fixture"
```

---

### Task 3: Sales Model Tests — Client, Supplier, Supply

**Files:**
- Modify: `tests/sales/test_models.py`

- [ ] **Step 1: Add Client, Supplier, Supply model tests**

Append to `tests/sales/test_models.py`:

```python
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
        # Prime the cache
        mf_map = ClientModel.get_mf_map()
        assert 'test123' in mf_map
        # Delete should invalidate
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
        # Supplier balance = CREDIT - DEBIT (we owe them)
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
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_models.py::TestClientModel tests/sales/test_models.py::TestSupplierModel tests/sales/test_models.py::TestSupplyModel -v`
Expected: 9 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_models.py
git commit -m "test: add Client, Supplier, Supply model tests"
```

---

### Task 4: Sales Model Tests — Purchase, PurchaseLine

**Files:**
- Modify: `tests/sales/test_models.py`

- [ ] **Step 1: Add Purchase and PurchaseLine model tests**

Append to `tests/sales/test_models.py`:

```python
@pytest.mark.django_db(transaction=True)
class TestPurchaseModel:
    def test_calculate_subtotal(self, tenant, seller):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory()
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('2.000'), unit_price=Decimal('50.000'))
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('3.000'), unit_price=Decimal('30.000'))
        # 2*50 + 3*30 = 100 + 90 = 190
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
        # FODEC = 1% of 1000 = 10, second line no FODEC
        assert purchase.calculate_total_fodec() == Decimal('1000.000') * Decimal('0.01')

    def test_calculate_tva_amount(self, tenant, seller):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory(tva=Decimal('19.00'), discount=Decimal('0.00'))
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('1000.000'))
        # subtotal_after_discount=1000, fodec=0, tva = (1000+0)*19/100 = 190
        assert purchase.calculate_tva_amount() == Decimal('190.000')

    def test_calculate_total(self, tenant, seller):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory(tva=Decimal('19.00'), discount=Decimal('0.00'), timbre_fiscal=Decimal('1.000'))
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('1000.000'))
        # subtotal=1000, tva=190, timbre=1 → total = 1000 + 190 + 1 = 1191
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
        # Should be sequential: 001-YEAR, 002-YEAR
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
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_models.py::TestPurchaseModel tests/sales/test_models.py::TestPurchaseLineModel -v`
Expected: 9 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_models.py
git commit -m "test: add Purchase and PurchaseLine model tests"
```

---

### Task 5: Sales Model Tests — Invoice (expanded), InvoiceService, CreditNote, Settings

**Files:**
- Modify: `tests/sales/test_models.py`

- [ ] **Step 1: Add expanded Invoice, InvoiceService, CreditNote model tests**

Append to `tests/sales/test_models.py` (these add tests not already covered by the existing `TestInvoiceCalculations` class):

```python
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
        # calculate_total_tva = subtotal_after_discount + FODEC + TVA (no timbre)
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
        # Need total > 1000D — use high enough unit_price
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
        # Manual retenu exists → auto returns 0
        assert invoice.get_auto_retenu_amount() == Decimal('0')

    def test_get_credit_notes_total(self, tenant, seller):
        from tests.factories import InvoiceFactory, CreditNoteFactory
        invoice = InvoiceFactory()
        CreditNoteFactory(client=invoice.client, invoice=invoice, amount_ht=Decimal('100.000'), tva=19)
        CreditNoteFactory(client=invoice.client, invoice=invoice, amount_ht=Decimal('200.000'), tva=19)
        total = invoice.get_credit_notes_total()
        # 100 + 19 + 200 + 38 = 357
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
        # Should be sequential
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
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_models.py::TestInvoiceModelExpanded tests/sales/test_models.py::TestInvoiceServiceModel tests/sales/test_models.py::TestCreditNoteModel tests/sales/test_models.py::TestSettingsModel -v`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_models.py
git commit -m "test: add expanded Invoice, InvoiceService, CreditNote, Settings model tests"
```

---

### Task 6: Sales Model Tests — BonLivraison, Devis, Service

**Files:**
- Modify: `tests/sales/test_models.py`

- [ ] **Step 1: Add BonLivraison, Devis, and Service model tests**

Append to `tests/sales/test_models.py`:

```python
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
        # Devis discount applies to (subtotal + FODEC) = (1000 + 10) * 10% = 101
        expected = (Decimal('1000.000') + Decimal('10.000')) * Decimal('10.00') / Decimal('100')
        assert devis.calculate_discount_amount() == expected

    def test_calculate_tva_amount(self, tenant, seller):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory(tva=Decimal('19.00'), discount=Decimal('0.00'))
        DevisServiceFactory(devis=devis, unit_price=Decimal('1000.000'))
        # TVA on (subtotal + FODEC - discount) = (1000 + 0 - 0) * 19% = 190
        assert devis.calculate_tva_amount() == Decimal('190.000')

    def test_calculate_total(self, tenant, seller):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory(tva=Decimal('19.00'), timbre_fiscal=Decimal('1.000'), discount=Decimal('0.00'))
        DevisServiceFactory(devis=devis, unit_price=Decimal('1000.000'))
        # subtotal=1000, fodec=0, discount=0, tva=190, timbre=1 → 1191
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
        # unit billing type falls through to price
        assert svc.total_price == Decimal('25.000')
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_models.py::TestBonLivraisonModel tests/sales/test_models.py::TestDevisModel tests/sales/test_models.py::TestServiceModel -v`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_models.py
git commit -m "test: add BonLivraison, Devis, Service model tests"
```

---

### Task 7: Utility Tests

**Files:**
- Create: `tests/sales/test_utilities.py`

- [ ] **Step 1: Create utility tests**

```python
import pytest
from decimal import Decimal


class TestNum2WordsTndFr:
    def test_zero(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('0'))
        assert result == 'zéro dinars'

    def test_one_dinar(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('1.000'))
        assert result == 'un dinar'

    def test_whole_dinars(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('1234.000'))
        assert 'mille deux cent trente-quatre' in result
        assert 'dinars' in result
        assert 'millime' not in result

    def test_millimes_only(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('0.500'))
        assert 'cinq cents millimes' in result

    def test_one_millime(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('0.001'))
        assert 'un millime' in result

    def test_mixed(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('42.750'))
        assert 'quarante-deux' in result
        assert 'dinars' in result
        assert 'sept cent cinquante' in result
        assert 'millimes' in result

    def test_rounding(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('1.9999'))
        # Rounds to 2.000
        assert 'deux dinars' in result

    def test_large_number(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('999999.999'))
        assert 'neuf cent quatre-vingt-dix-neuf mille' in result
```

Note: These tests don't need `@pytest.mark.django_db` — they're pure Python.

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_utilities.py -v`
Expected: 8 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_utilities.py
git commit -m "test: add num2words_tnd_fr utility tests"
```

---

### Task 8: Retenu Model Tests

**Files:**
- Create: `tests/payment/test_retenu_models.py`

- [ ] **Step 1: Create retenu model tests**

```python
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
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/payment/test_retenu_models.py -v`
Expected: 6 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/payment/test_retenu_models.py
git commit -m "test: add retenu model tests"
```

---

### Task 9: Invoice View Tests

**Files:**
- Create: `tests/sales/test_invoice_views.py`

- [ ] **Step 1: Create invoice view tests**

```python
import pytest
from decimal import Decimal
from unittest.mock import patch
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestInvoiceViews:
    def test_invoice_list_requires_login(self, tenant, seller):
        from django.test import Client
        client = Client()
        resp = client.get(reverse('invoices_list'))
        assert resp.status_code == 302
        assert 'login' in resp.url or resp.url == '/'

    def test_invoice_list_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('invoices_list'))
        assert resp.status_code == 200

    def test_invoice_list_search(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory
        inv = InvoiceFactory(title='Special Invoice')
        resp = logged_in_client.get(reverse('invoices_list'), {'search': 'Special'})
        assert resp.status_code == 200

    def test_invoice_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        client = ClientFactory()
        service = ServiceFactory()
        resp = logged_in_client.post(reverse('invoice_create'), {
            'client': client.id,
            'service_id[]': [service.id],
            'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'],
            'tva': '19',
            'timbre_fiscal': '1.000',
            'discount': '0',
        })
        assert resp.status_code == 302
        from sales.models import Invoice
        assert Invoice.objects.filter(client=client).exists()

    def test_invoice_create_no_client(self, tenant, seller, logged_in_client):
        resp = logged_in_client.post(reverse('invoice_create'), {})
        assert resp.status_code == 302  # redirects with error

    def test_invoice_create_no_services(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        client = ClientFactory()
        resp = logged_in_client.post(reverse('invoice_create'), {
            'client': client.id,
        })
        assert resp.status_code == 302  # redirects with error

    def test_invoice_create_ledger_debit(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import ClientTransaction
        client = ClientFactory()
        service = ServiceFactory()
        logged_in_client.post(reverse('invoice_create'), {
            'client': client.id,
            'service_id[]': [service.id],
            'unit_price[]': ['1000.000'],
            'has_fodec[]': ['0'],
            'tva': '19',
            'timbre_fiscal': '1.000',
            'discount': '0',
        })
        txn = ClientTransaction.objects.filter(client=client, transaction_type='DEBIT').first()
        assert txn is not None
        assert txn.source == 'INVOICE_CREATED'

    def test_invoice_detail_renders(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()
        resp = logged_in_client.get(reverse('invoice_detail', args=[invoice.id]))
        assert resp.status_code == 200

    def test_invoice_edit_updates_fields(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ServiceFactory
        invoice = InvoiceFactory()
        service = ServiceFactory()
        resp = logged_in_client.post(reverse('invoice_edit', args=[invoice.id]), {
            'status': 'CONFIRMED',
            'notes': 'Updated note',
            'tva': '19',
            'timbre_fiscal': '1.000',
            'discount': '5',
            'client': invoice.client.id,
            'service_id[]': [service.id],
            'unit_price[]': ['200.000'],
            'has_fodec[]': ['0'],
        })
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.status == 'CONFIRMED'
        assert invoice.notes == 'Updated note'

    def test_invoice_delete_removes_ledger(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ClientTransactionFactory
        invoice = InvoiceFactory()
        ClientTransactionFactory(client=invoice.client, invoice=invoice, transaction_type='DEBIT')
        logged_in_client.post(reverse('invoice_delete', args=[invoice.id]))
        from sales.models import ClientTransaction, Invoice
        assert not Invoice.objects.filter(pk=invoice.pk).exists()
        assert not ClientTransaction.objects.filter(invoice=invoice).exists()

    def test_invoice_delete_post_only(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()
        resp = logged_in_client.get(reverse('invoice_delete', args=[invoice.id]))
        assert resp.status_code == 302
        from sales.models import Invoice
        assert Invoice.objects.filter(pk=invoice.pk).exists()
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_invoice_views.py -v`
Expected: 11 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_invoice_views.py
git commit -m "test: add invoice view tests"
```

---

### Task 10: Credit Note View Tests

**Files:**
- Create: `tests/sales/test_credit_note_views.py`

- [ ] **Step 1: Create credit note view tests**

```python
import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestCreditNoteViews:
    def test_avoir_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import CreditNote, ClientTransaction
        client = ClientFactory()
        resp = logged_in_client.post(reverse('avoir_create'), {
            'client': client.id,
            'description': 'Test avoir',
            'amount_ht': '500.000',
            'tva': '19',
        })
        assert resp.status_code == 302
        assert CreditNote.objects.filter(client=client).exists()
        txn = ClientTransaction.objects.filter(client=client, source='AVOIR_CREATED').first()
        assert txn is not None
        assert txn.transaction_type == 'CREDIT'

    def test_avoir_create_no_description(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        client = ClientFactory()
        resp = logged_in_client.post(reverse('avoir_create'), {
            'client': client.id,
            'amount_ht': '500.000',
        })
        assert resp.status_code == 302
        from sales.models import CreditNote
        assert not CreditNote.objects.filter(client=client).exists()

    def test_avoir_create_no_amount(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        client = ClientFactory()
        resp = logged_in_client.post(reverse('avoir_create'), {
            'client': client.id,
            'description': 'Test',
        })
        assert resp.status_code == 302
        from sales.models import CreditNote
        assert not CreditNote.objects.filter(client=client).exists()

    def test_avoir_create_with_linked_invoice(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, InvoiceFactory
        client = ClientFactory()
        invoice = InvoiceFactory(client=client)
        logged_in_client.post(reverse('avoir_create'), {
            'client': client.id,
            'description': 'Linked avoir',
            'amount_ht': '100.000',
            'invoice_id': invoice.id,
        })
        from sales.models import CreditNote
        cn = CreditNote.objects.filter(client=client).first()
        assert cn is not None
        assert cn.invoice == invoice

    def test_avoir_delete_post_only(self, tenant, seller, logged_in_client):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory()
        resp = logged_in_client.get(reverse('avoir_delete', args=[cn.id]))
        # GET should not delete
        from sales.models import CreditNote
        assert CreditNote.objects.filter(pk=cn.pk).exists()

    def test_avoir_detail_renders(self, tenant, seller, logged_in_client):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory()
        resp = logged_in_client.get(reverse('avoir_detail', args=[cn.id]))
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_credit_note_views.py -v`
Expected: 6 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_credit_note_views.py
git commit -m "test: add credit note view tests"
```

---

### Task 11: Client View Tests

**Files:**
- Create: `tests/sales/test_client_views.py`

- [ ] **Step 1: Create client view tests**

```python
import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestClientViews:
    def test_clients_list_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('clients'))
        assert resp.status_code == 200

    def test_clients_list_search(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        ClientFactory(clientname='UniqueSearchName')
        resp = logged_in_client.get(reverse('clients'), {'search': 'UniqueSearchName'})
        assert resp.status_code == 200

    def test_edit_client_updates_fields(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        client = ClientFactory()
        logged_in_client.post(reverse('edit_client', args=[client.id]), {
            'clientname': 'Updated Name',
            'emailAddress': 'new@test.com',
            'adress': 'New Address',
            'mf': 'NEWMF123',
        })
        client.refresh_from_db()
        assert client.clientname == 'Updated Name'

    def test_delete_client(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import Client
        client = ClientFactory()
        logged_in_client.get(reverse('delete-client', args=[client.pk]))
        assert not Client.objects.filter(pk=client.pk).exists()

    def test_client_add_transaction_manual(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import ClientTransaction
        client = ClientFactory()
        logged_in_client.post(reverse('client_add_transaction', args=[client.id]), {
            'transaction_type': 'DEBIT',
            'amount': '250.000',
            'description': 'Manual debit',
        })
        txn = ClientTransaction.objects.filter(client=client).first()
        assert txn is not None
        assert txn.source == 'MANUAL'
        assert txn.amount == Decimal('250.000')

    def test_client_add_credit_updates_invoice_paid(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, InvoiceFactory, InvoiceServiceFactory
        client = ClientFactory()
        invoice = InvoiceFactory(client=client, tva=19, discount=0)
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))
        logged_in_client.post(reverse('client_add_transaction', args=[client.id]), {
            'transaction_type': 'CREDIT',
            'amount': '500.000',
            'description': 'Partial payment',
            'invoice_id': invoice.id,
        })
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('500.000')

    def test_client_add_credit_marks_paid(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, InvoiceFactory, InvoiceServiceFactory
        client = ClientFactory()
        invoice = InvoiceFactory(client=client, tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        total = invoice.calculate_total()
        logged_in_client.post(reverse('client_add_transaction', args=[client.id]), {
            'transaction_type': 'CREDIT',
            'amount': str(total),
            'description': 'Full payment',
            'invoice_id': invoice.id,
        })
        invoice.refresh_from_db()
        assert invoice.status == 'PAID'

    def test_client_delete_transaction(self, tenant, seller, logged_in_client):
        from tests.factories import ClientTransactionFactory
        txn = ClientTransactionFactory()
        resp = logged_in_client.post(reverse('client_delete_transaction', args=[txn.id]))
        assert resp.status_code == 200
        from sales.models import ClientTransaction
        assert not ClientTransaction.objects.filter(pk=txn.pk).exists()

    def test_client_unpaid_invoices_json(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, InvoiceFactory
        client = ClientFactory()
        InvoiceFactory(client=client, status='CURRENT')
        resp = logged_in_client.get(reverse('client_unpaid_invoices', args=[client.id]))
        assert resp.status_code == 200

    def test_mf_map_returns_json(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        ClientFactory(mf='TESTMF999')
        resp = logged_in_client.get(reverse('mf_map'))
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_client_views.py -v`
Expected: 10 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_client_views.py
git commit -m "test: add client view tests"
```

---

### Task 12: Supplier View Tests

**Files:**
- Create: `tests/sales/test_supplier_views.py`

- [ ] **Step 1: Create supplier view tests**

```python
import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestSupplierViews:
    def test_suppliers_list_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('suppliers'))
        assert resp.status_code == 200

    def test_edit_supplier_updates_fields(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory
        supplier = SupplierFactory()
        logged_in_client.post(reverse('edit_supplier', args=[supplier.id]), {
            'name': 'Updated Supplier',
            'emailAddress': 'supplier@test.com',
            'adress': 'New Supplier St',
            'mf': 'NEWMF456',
        })
        supplier.refresh_from_db()
        assert supplier.name == 'Updated Supplier'

    def test_delete_supplier(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory
        from sales.models import Supplier
        supplier = SupplierFactory()
        logged_in_client.get(reverse('delete-supplier', args=[supplier.pk]))
        assert not Supplier.objects.filter(pk=supplier.pk).exists()

    def test_supplier_add_transaction(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory
        from sales.models import SupplierTransaction
        supplier = SupplierFactory()
        logged_in_client.post(reverse('supplier_add_transaction', args=[supplier.id]), {
            'transaction_type': 'CREDIT',
            'amount': '300.000',
            'description': 'Manual credit',
        })
        txn = SupplierTransaction.objects.filter(supplier=supplier).first()
        assert txn is not None
        assert txn.source == 'MANUAL'

    def test_supplier_transactions_json(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory, SupplierTransactionFactory
        supplier = SupplierFactory()
        SupplierTransactionFactory(supplier=supplier)
        resp = logged_in_client.get(reverse('supplier_transactions', args=[supplier.id]))
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_supplier_views.py -v`
Expected: 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_supplier_views.py
git commit -m "test: add supplier view tests"
```

---

### Task 13: Purchase View Tests

**Files:**
- Create: `tests/sales/test_purchase_views.py`

- [ ] **Step 1: Create purchase view tests**

```python
import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestPurchaseViews:
    def test_purchase_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory, SupplyFactory
        from sales.models import Purchase
        supplier = SupplierFactory()
        supply = SupplyFactory()
        resp = logged_in_client.post(reverse('purchase_create'), {
            'supplier': supplier.id,
            'supply_id[]': [supply.id],
            'quantity[]': ['5.000'],
            'line_unit_price[]': ['10.000'],
            'tva': '19.00',
            'discount': '0.00',
            'timbre_fiscal': '1.000',
        })
        assert resp.status_code == 302
        assert Purchase.objects.filter(supplier=supplier).exists()

    def test_purchase_confirm_increments_stock(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory, SupplyFactory
        supply = SupplyFactory(stock_quantity=Decimal('100.000'))
        purchase = PurchaseFactory(status='DRAFT')
        PurchaseLineFactory(purchase=purchase, supply=supply, quantity=Decimal('20.000'))
        logged_in_client.post(reverse('purchase_confirm', args=[purchase.id]))
        supply.refresh_from_db()
        assert supply.stock_quantity == Decimal('120.000')

    def test_purchase_confirm_creates_supplier_credit(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        from sales.models import SupplierTransaction
        purchase = PurchaseFactory(status='DRAFT')
        PurchaseLineFactory(purchase=purchase, quantity=Decimal('1.000'), unit_price=Decimal('1000.000'))
        logged_in_client.post(reverse('purchase_confirm', args=[purchase.id]))
        txn = SupplierTransaction.objects.filter(purchase=purchase, transaction_type='CREDIT').first()
        assert txn is not None
        assert txn.source == 'PURCHASE_CONFIRMED'

    def test_purchase_confirm_sets_received(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory(status='DRAFT')
        PurchaseLineFactory(purchase=purchase)
        logged_in_client.post(reverse('purchase_confirm', args=[purchase.id]))
        purchase.refresh_from_db()
        assert purchase.status == 'RECEIVED'

    def test_purchase_confirm_already_paid(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory
        purchase = PurchaseFactory(status='PAID')
        resp = logged_in_client.post(reverse('purchase_confirm', args=[purchase.id]))
        assert resp.status_code == 302
        purchase.refresh_from_db()
        assert purchase.status == 'PAID'  # unchanged

    def test_purchase_payment_creates_debit(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        from sales.models import SupplierTransaction
        purchase = PurchaseFactory(status='RECEIVED')
        PurchaseLineFactory(purchase=purchase)
        logged_in_client.post(reverse('process_purchase_payment', args=[purchase.id]))
        txn = SupplierTransaction.objects.filter(purchase=purchase, transaction_type='DEBIT').first()
        assert txn is not None
        assert txn.source == 'PURCHASE_PAID'

    def test_purchase_payment_sets_paid(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory, PurchaseLineFactory
        purchase = PurchaseFactory(status='RECEIVED')
        PurchaseLineFactory(purchase=purchase)
        logged_in_client.post(reverse('process_purchase_payment', args=[purchase.id]))
        purchase.refresh_from_db()
        assert purchase.status == 'PAID'

    def test_purchase_payment_already_paid(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory
        purchase = PurchaseFactory(status='PAID')
        resp = logged_in_client.post(reverse('process_purchase_payment', args=[purchase.id]))
        assert resp.status_code == 302

    def test_purchase_delete(self, tenant, seller, logged_in_client):
        from tests.factories import PurchaseFactory
        from sales.models import Purchase
        purchase = PurchaseFactory()
        logged_in_client.post(reverse('purchase_delete', args=[purchase.id]))
        assert not Purchase.objects.filter(pk=purchase.pk).exists()
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_purchase_views.py -v`
Expected: 9 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_purchase_views.py
git commit -m "test: add purchase view tests"
```

---

### Task 14: Devis View Tests

**Files:**
- Create: `tests/sales/test_devis_views.py`

- [ ] **Step 1: Create devis view tests**

```python
import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestDevisViews:
    def test_devis_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Devis, InvoiceService
        client = ClientFactory()
        service = ServiceFactory()
        resp = logged_in_client.post(reverse('devis_create'), {
            'client': client.id,
            'title': 'Test Devis',
            'service_id[]': [service.id],
            'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'],
            'hours_used[]': [''],
            'days_used[]': [''],
            'units_used[]': [''],
            'tva': '19',
            'timbre_fiscal': '1.000',
            'discount': '0',
        })
        assert resp.status_code == 302
        devis = Devis.objects.filter(client=client).first()
        assert devis is not None
        # InvoiceService should be linked to devis, not invoice
        assert InvoiceService.objects.filter(devis=devis).exists()

    def test_devis_update_fields(self, tenant, seller, logged_in_client):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory(title='Original')
        DevisServiceFactory(devis=devis)
        logged_in_client.post(reverse('devis_update', args=[devis.id]), {
            'title': 'Updated Title',
            'notes': 'New notes',
            'discount': '5',
        })
        devis.refresh_from_db()
        assert devis.title == 'Updated Title'

    def test_devis_convert_creates_invoice(self, tenant, seller, logged_in_client):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory()
        DevisServiceFactory(devis=devis)
        resp = logged_in_client.post(reverse('devis_convert', args=[devis.id]))
        assert resp.status_code == 302
        devis.refresh_from_db()
        assert devis.status == 'ACCEPTED'
        assert devis.converted_invoice is not None

    def test_devis_convert_already_converted(self, tenant, seller, logged_in_client):
        from tests.factories import DevisFactory, DevisServiceFactory, InvoiceFactory
        invoice = InvoiceFactory()
        devis = DevisFactory(converted_invoice=invoice, status='ACCEPTED')
        resp = logged_in_client.post(reverse('devis_convert', args=[devis.id]))
        assert resp.status_code == 302

    def test_devis_delete(self, tenant, seller, logged_in_client):
        from tests.factories import DevisFactory
        from sales.models import Devis
        devis = DevisFactory()
        logged_in_client.post(reverse('devis_delete', args=[devis.id]))
        assert not Devis.objects.filter(pk=devis.pk).exists()
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_devis_views.py -v`
Expected: 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_devis_views.py
git commit -m "test: add devis view tests"
```

---

### Task 15: Bon de Livraison, Service, Settings View Tests

**Files:**
- Create: `tests/sales/test_bon_livraison_views.py`
- Create: `tests/sales/test_service_views.py`
- Create: `tests/sales/test_settings_views.py`

- [ ] **Step 1: Create bon de livraison view tests**

```python
import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestBonLivraisonViews:
    def test_bon_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import BonLivraison
        client = ClientFactory()
        resp = logged_in_client.post(reverse('bon_livraison_create'), {
            'client': client.id,
            'tva': '19.000',
            'description[]': ['Item 1', 'Item 2'],
            'amount[]': ['100.000', '200.000'],
        })
        assert resp.status_code == 302
        assert BonLivraison.objects.filter(client=client).exists()

    def test_bon_detail_renders(self, tenant, seller, logged_in_client):
        from tests.factories import BonLivraisonFactory, BonLivraisonLineFactory
        bon = BonLivraisonFactory()
        BonLivraisonLineFactory(bon=bon)
        resp = logged_in_client.get(reverse('bon_livraison_detail', args=[bon.id]))
        assert resp.status_code == 200

    def test_bon_edit_rebuilds_lines(self, tenant, seller, logged_in_client):
        from tests.factories import BonLivraisonFactory, BonLivraisonLineFactory
        from sales.models import BonLivraisonLine
        bon = BonLivraisonFactory()
        BonLivraisonLineFactory(bon=bon)
        logged_in_client.post(reverse('bon_livraison_edit', args=[bon.id]), {
            'client': bon.client.id,
            'tva': '19.000',
            'description[]': ['New Item'],
            'amount[]': ['500.000'],
        })
        assert BonLivraisonLine.objects.filter(bon=bon).count() == 1
        assert BonLivraisonLine.objects.filter(bon=bon).first().amount == Decimal('500.000')

    def test_bon_delete(self, tenant, seller, logged_in_client):
        from tests.factories import BonLivraisonFactory
        from sales.models import BonLivraison
        bon = BonLivraisonFactory()
        logged_in_client.post(reverse('bon_livraison_delete', args=[bon.id]))
        assert not BonLivraison.objects.filter(pk=bon.pk).exists()
```

- [ ] **Step 2: Create service view tests**

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestServiceViews:
    def test_service_list_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('services_list'))
        assert resp.status_code == 200

    def test_service_list_search(self, tenant, seller, logged_in_client):
        from tests.factories import ServiceFactory
        ServiceFactory(title='UniqueServiceName')
        resp = logged_in_client.get(reverse('services_list'), {'search': 'UniqueServiceName'})
        assert resp.status_code == 200

    def test_add_service(self, tenant, seller, logged_in_client):
        from sales.models import Service
        resp = logged_in_client.post(reverse('add_service'), {
            'title': 'New Service',
            'billing_type': 'flat',
            'price': '100.000',
            'currency': 'TND',
            'service_type': 'service',
        })
        assert resp.status_code == 302
        assert Service.objects.filter(title='New Service').exists()

    def test_delete_service(self, tenant, seller, logged_in_client):
        from tests.factories import ServiceFactory
        from sales.models import Service
        svc = ServiceFactory()
        logged_in_client.post(reverse('delete_service', args=[svc.id]))
        assert not Service.objects.filter(pk=svc.pk).exists()
```

- [ ] **Step 3: Create settings view tests**

```python
import pytest
from unittest.mock import patch
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestSettingsViews:
    def test_settings_view_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('settings_view'))
        assert resp.status_code == 200

    def test_settings_save_updates_fields(self, tenant, seller, logged_in_client):
        with patch('sales.models._sync_ngsign_org'):
            resp = logged_in_client.post(reverse('settings_view'), {
                'clientname': 'Updated Company',
                'mf': seller.mf,
                'adress': 'New Address',
                'tva': '19.00',
                'dt': '1.000',
            })
        assert resp.status_code == 302
        seller.refresh_from_db()
        assert seller.clientname == 'Updated Company'

    def test_company_logo_serves_base64(self, tenant, logged_in_client):
        from sales.models import Settings
        from unittest.mock import patch
        with patch('sales.models._sync_ngsign_org'):
            s = Settings.objects.create(
                clientname='Logo Co',
                clientLogo='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            )
        resp = logged_in_client.get(reverse('company_logo'))
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'image/png'
```

- [ ] **Step 4: Run all three test files**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_bon_livraison_views.py tests/sales/test_service_views.py tests/sales/test_settings_views.py -v`
Expected: 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/sales/test_bon_livraison_views.py tests/sales/test_service_views.py tests/sales/test_settings_views.py
git commit -m "test: add bon de livraison, service, and settings view tests"
```

---

### Task 16: Payment View Tests

**Files:**
- Create: `tests/payment/test_payment_views.py`

- [ ] **Step 1: Create payment view tests**

```python
import pytest
from decimal import Decimal
from unittest.mock import patch
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestProcessPayment:
    def _make_invoice_with_total(self, seller, total_approx):
        """Helper: create an invoice with a service priced to hit roughly `total_approx`."""
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        # unit_price that gives total ≈ total_approx
        # total = unit_price + unit_price*0.19 + 1 = unit_price * 1.19 + 1
        unit_price = (total_approx - Decimal('1.000')) / Decimal('1.19')
        InvoiceServiceFactory(invoice=invoice, unit_price=unit_price.quantize(Decimal('0.001')))
        return invoice

    def test_process_payment_partial(self, tenant, seller, logged_in_client):
        invoice = self._make_invoice_with_total(seller, Decimal('500.000'))
        resp = logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': '100.000',
        })
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('100.000')
        assert invoice.status == 'CURRENT'

    def test_process_payment_full(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        total = invoice.calculate_total()
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': str(total),
        })
        invoice.refresh_from_db()
        assert invoice.status == 'PAID'

    def test_process_payment_clamps_to_remaining(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        total = invoice.calculate_total()
        # Try to pay more than total
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': str(total + Decimal('999.000')),
        })
        invoice.refresh_from_db()
        assert invoice.amount_paid == total

    def test_process_payment_zero_amount(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        resp = logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': '0',
        })
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('0.000')

    def test_process_payment_with_credit_notes(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory, CreditNoteFactory
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('1000.000'))
        CreditNoteFactory(client=invoice.client, invoice=invoice, amount_ht=Decimal('100.000'), tva=19)
        total = invoice.calculate_total()
        cn_total = invoice.get_credit_notes_total()
        effective = total - cn_total
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': str(effective),
        })
        invoice.refresh_from_db()
        assert invoice.status == 'PAID'

    def test_process_payment_with_auto_retenu(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        from unittest.mock import patch
        # Set default_retenu_rate on Settings so auto_retenu kicks in
        seller.default_retenu_rate = Decimal('1.5')
        with patch('sales.models._sync_ngsign_org'):
            seller.save()
        # Create invoice with total > 1000 D
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('2000.000'))
        total = invoice.calculate_total()
        auto_retenu = invoice.get_auto_retenu_amount()
        assert auto_retenu > Decimal('0')
        effective = total - auto_retenu
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': str(effective),
        })
        invoice.refresh_from_db()
        assert invoice.status == 'PAID'

    def test_process_payment_creates_ledger_credit(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, InvoiceServiceFactory
        from sales.models import ClientTransaction
        invoice = InvoiceFactory(tva=19, discount=0, timbre_fiscal=Decimal('1.000'))
        InvoiceServiceFactory(invoice=invoice, unit_price=Decimal('100.000'))
        logged_in_client.post(reverse('process_payment', args=[invoice.id]), {
            'payment_amount': '50.000',
        })
        txn = ClientTransaction.objects.filter(
            invoice=invoice, transaction_type='CREDIT', source='INVOICE_PAID'
        ).first()
        assert txn is not None
        assert txn.amount == Decimal('50.000')


@pytest.mark.django_db(transaction=True)
class TestRetenuAjax:
    def test_get_retenu_rate_json(self, tenant, seller, logged_in_client):
        from tests.factories import RetenuFactory
        retenu = RetenuFactory(
            category='LOYERS',
            subcategory='LOYER_RESIDENT',
            rate=Decimal('10.00'),
        )
        resp = logged_in_client.get(reverse('get_retenu_rate', args=[retenu.id]))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['rate'] == 10.0

    def test_calculate_retenu_preview(self, tenant, seller, logged_in_client):
        from tests.factories import RetenuFactory
        retenu = RetenuFactory(rate=Decimal('5.00'))
        resp = logged_in_client.get(reverse('calculate_retenu_preview'), {
            'retenu_id': retenu.id,
            'base_amount': '2000.000',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['calculated_amount'] == 100.0
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/payment/test_payment_views.py -v`
Expected: 10 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/payment/test_payment_views.py
git commit -m "test: add payment view tests"
```

---

### Task 17: Run Full Suite and Coverage Report

- [ ] **Step 1: Run full Phase 1 + Phase 2 test suite**

Run: `cd "invoice app service" && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (Phase 1 gov tests + Phase 2 sales/payment tests)

- [ ] **Step 2: Run with coverage**

Run: `cd "invoice app service" && python -m pytest tests/ --cov=invoice/sales --cov=invoice/payment --cov=invoice/gov -v --tb=short`
Expected: Coverage report showing improved coverage for sales/models.py, sales/views.py, payment/models.py, payment/views.py

- [ ] **Step 3: Commit any final adjustments**

If any tests needed fixing, commit the fixes.

- [ ] **Step 4: Push to remote**

```bash
git push origin feature/ngsign-integration
```
