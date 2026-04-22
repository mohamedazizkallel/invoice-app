import factory
from factory.django import DjangoModelFactory
from django.utils import timezone
from decimal import Decimal


class ClientFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Client'

    clientname = factory.Sequence(lambda n: f'Client {n}')
    mf = factory.Sequence(lambda n: f'1234567ABM{n:03d}')
    adress = '123 Rue Test, Tunis'
    emailAddress = factory.LazyAttribute(
        lambda o: f'{o.clientname.lower().replace(" ", "")}@test.com'
    )


class ServiceFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Service'

    title = factory.Sequence(lambda n: f'Service {n}')
    description = 'Test service description'
    billing_type = 'flat'
    price = factory.LazyFunction(lambda: __import__('decimal').Decimal('100.000'))


class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Invoice'

    client = factory.SubFactory(ClientFactory)
    uniqueId = factory.Sequence(lambda n: f'FA-{n:03d}-2026')
    date_created = factory.LazyFunction(timezone.now)
    status = 'CURRENT'
    tva = 19
    discount = 0


class InvoiceServiceFactory(DjangoModelFactory):
    """Creates a line item linking an Invoice to a Service."""
    class Meta:
        model = 'sales.InvoiceService'

    invoice = factory.SubFactory(InvoiceFactory)
    service = factory.SubFactory(ServiceFactory)
    unit_price = factory.LazyFunction(lambda: __import__('decimal').Decimal('100.000'))
    hours_used = None
    days_used = None
    units_used = None
    has_fodec = False


class CreditNoteFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.CreditNote'

    client = factory.SubFactory(ClientFactory)
    uniqueId = factory.Sequence(lambda n: f'AV-{n:03d}-2026')
    description = 'Test credit note'
    amount_ht = factory.LazyFunction(lambda: __import__('decimal').Decimal('500.000'))
    tva = 19


class SettingsFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Settings'

    clientname = 'Test Company SARL'
    mf = '9876543XYZ000'
    adress = '123 Rue Test, Tunis'
    emailAddress = 'test@company.tn'


class GovInvoiceFactory(DjangoModelFactory):
    class Meta:
        model = 'gov.GovInvoice'
        exclude = ['use_credit_note']

    use_credit_note = False

    invoice = factory.Maybe(
        'use_credit_note',
        yes_declaration=None,
        no_declaration=factory.SubFactory(InvoiceFactory),
    )
    credit_note = factory.Maybe(
        'use_credit_note',
        yes_declaration=factory.SubFactory(CreditNoteFactory),
        no_declaration=None,
    )
    unsigned_xml = b'<TEIF>test</TEIF>'
    status = 'draft'
    ngsign_status = None


class NGSignClientAccountFactory(DjangoModelFactory):
    class Meta:
        model = 'tenants.NGSignClientAccount'

    # tenant must be provided explicitly — lives in public schema
    org_uuid = factory.Faker('uuid4')
    org_jwt = 'test-org-jwt-token'
    signer_email = 'signer@test.com'
    status = 'ACTIVE'


# ── Phase 2 factories ────────────────────────────────────────

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
