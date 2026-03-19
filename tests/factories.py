import factory
from factory.django import DjangoModelFactory
from django.utils import timezone


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
    # date_created uses auto_now_add=True — cannot be overridden
    description = 'Test credit note'
    amount_ht = factory.LazyFunction(lambda: __import__('decimal').Decimal('500.000'))
    tva = 19


class SettingsFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Settings'

    clientname = 'Test Company SARL'
    mf = '9876543XYZ000'
    adress = '123 Rue Test, Tunis'


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
