# Testing Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish pytest infrastructure and write comprehensive tests for the NGSign integration (async submission, notification API, service layer, client module, serializer, TEIF builder), then expand to broad app coverage.

**Architecture:** pytest + pytest-django as test runner, factory-boy for test data, `responses` library for HTTP-level mocking of NGSign API, `unittest.mock.patch` for service/view-level mocking, `freezegun` for time-dependent tests. All tests run against real PostgreSQL with django-tenants schema isolation.

**Tech Stack:** pytest, pytest-django, pytest-cov, factory-boy, responses, freezegun, lxml (already installed)

**Spec:** `docs/superpowers/specs/2026-03-18-testing-strategy-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `requirements-dev.txt` | Dev/test dependencies (includes production via `-r requirements.txt`) |
| `pytest.ini` | pytest configuration: Django settings, test paths, coverage |
| `tests/__init__.py` | Package init |
| `tests/conftest.py` | Shared fixtures: tenant setup, user, auth client, seller, ngsign_account |
| `tests/factories.py` | factory-boy factories for all models |
| `tests/gov/__init__.py` | Package init |
| `tests/gov/test_ngsign_client.py` | HTTP-level tests for NGSign client (uses `responses`) |
| `tests/gov/test_ngsign_service.py` | Service layer tests (submit_invoice, check_status) |
| `tests/gov/test_ngsign_serializer.py` | serializer.build_payload tests |
| `tests/gov/test_teif_builder.py` | TEIF XML generation tests |
| `tests/gov/test_async_submission.py` | Async submit views, thread function, check views |
| `tests/gov/test_notification_api.py` | ngsign_pending_api endpoint tests |
| `tests/sales/__init__.py` | Package init |
| `tests/sales/test_models.py` | Invoice/CreditNote business logic tests |
| `tests/payment/__init__.py` | Package init |

---

### Task 1: Test Infrastructure Setup

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/factories.py`
- Create: `tests/gov/__init__.py`
- Create: `tests/sales/__init__.py`
- Create: `tests/payment/__init__.py`

**Context:** The project has zero test infrastructure. No pytest, no test deps, no conftest. We need to set up everything from scratch. The app uses django-tenants (multi-tenant PostgreSQL), so the conftest must create a test tenant + schema before any test runs, and clean it up after. `Settings.save()` triggers `_sync_ngsign_org` via `on_commit` which makes real NGSign API calls — the `seller` fixture must mock this.

**Reference files:**
- `invoice/tenants/models.py` — `Tenant`, `Domain`, `NGSignClientAccount` models
- `invoice/gov/models.py` — `GovInvoice` model
- `invoice/sales/models.py` — `Client`, `Invoice`, `InvoiceService`, `CreditNote`, `Service`, `Settings` models

- [ ] **Step 1: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.5
pytest-django==4.9.0
pytest-cov==6.1.1
factory-boy==3.3.3
responses==0.25.7
freezegun==1.4.0
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
DJANGO_SETTINGS_MODULE = invoice.settings
pythonpath = invoice
testpaths = tests
addopts = --cov=invoice/gov --cov=invoice/sales --cov=invoice/payment --cov-report=term-missing --tb=short
```

Note: `--cov` uses filesystem paths relative to project root, not Python package names. `pythonpath = invoice` makes imports like `from gov.models import GovInvoice` work.

- [ ] **Step 3: Create package init files**

Create empty `__init__.py` files:
- `tests/__init__.py`
- `tests/gov/__init__.py`
- `tests/sales/__init__.py`
- `tests/payment/__init__.py`

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import pytest
from unittest.mock import patch
from django.db import connection


@pytest.fixture(scope='session')
def tenant_setup(django_db_setup, django_db_blocker):
    """Create a test tenant and switch to its schema. Runs once per test session."""
    with django_db_blocker.unblock():
        from tenants.models import Tenant, Domain
        tenant = Tenant(schema_name='test_tenant', name='Test Tenant')
        tenant.save()
        Domain.objects.create(domain='test.localhost', tenant=tenant, is_primary=True)
        connection.set_schema('test_tenant')
    yield tenant
    with django_db_blocker.unblock():
        connection.set_schema_to_public()
        tenant.delete(force_drop=True)


@pytest.fixture
def tenant(tenant_setup, db):
    """Per-test fixture that ensures tenant schema is active."""
    connection.set_schema('test_tenant')
    return tenant_setup


@pytest.fixture
def user(tenant):
    """Create a test user in the tenant schema."""
    from django.contrib.auth.models import User
    return User.objects.create_user(username='testuser', password='testpass123')


@pytest.fixture
def logged_in_client(user):
    """Return an authenticated Django test client."""
    from django.test import Client
    client = Client()
    client.login(username='testuser', password='testpass123')
    return client


@pytest.fixture
def seller(tenant):
    """Create a Settings (seller) instance.
    Mocks _sync_ngsign_org to prevent real NGSign API calls on Settings.save()."""
    from tests.factories import SettingsFactory
    with patch('sales.models._sync_ngsign_org'):
        return SettingsFactory()


@pytest.fixture
def ngsign_account(tenant_setup, db):
    """Create an NGSignClientAccount in the public schema for the test tenant."""
    current = connection.schema_name
    connection.set_schema_to_public()
    from tests.factories import NGSignClientAccountFactory
    account = NGSignClientAccountFactory(tenant=tenant_setup)
    connection.set_schema(current)
    return account
```

- [ ] **Step 5: Create `tests/factories.py`**

```python
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
```

- [ ] **Step 6: Install dev dependencies**

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 7: Verify pytest discovers no tests yet**

Run: `cd "invoice app service" && python -m pytest --co -q 2>&1 | head -5`
Expected: `no tests ran` or `0 items collected`

- [ ] **Step 8: Commit**

```bash
git add requirements-dev.txt pytest.ini tests/
git commit -m "feat: add pytest infrastructure, conftest fixtures, and factory-boy factories"
```

---

### Task 2: NGSign Client Tests

**Files:**
- Create: `tests/gov/test_ngsign_client.py`

**Context:** The NGSign client module (`invoice/gov/ngsign/client.py`) makes HTTP calls to the NGSign sandbox API. We use the `responses` library to mock all HTTP calls at the `requests` level. Each function has a specific URL, auth header format, and response parsing pattern. No DB access needed for most of these tests — they're pure HTTP.

**Reference files:**
- `invoice/gov/ngsign/client.py` — the module under test
- `invoice/gov/ngsign/exceptions.py` — `NGSignAPIError`, `NGSignAuthError`

**Constants from client.py:**
- `INVOICE_API_BASE = 'https://sandbox.ng-sign.com/server'`
- `PARTNER_API_BASE = 'https://sandbox.ng-sign.com'`
- `PDS_BASE = 'https://sandbox.ng-sign.com/pds/#/teif/invoice'`

- [ ] **Step 1: Write the tests**

```python
import base64
import pytest
import responses
from gov.ngsign.client import (
    create_transaction, check_invoice_status, get_signed_xml,
    get_pds_url, create_org, update_org, refresh_jwt,
    INVOICE_API_BASE, PARTNER_API_BASE, PDS_BASE,
)
from gov.ngsign.exceptions import NGSignAPIError, NGSignAuthError


class TestCreateTransaction:
    @responses.activate
    def test_posts_correct_url(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        responses.post(url, json={'object': {'uuid': 'txn-123', 'invoices': []}}, status=200)

        create_transaction('org-jwt', [{'invoiceFileB64': 'abc'}], 'signer@test.com')

        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @responses.activate
    def test_sends_auth_header(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        responses.post(url, json={'object': {'uuid': 'txn-123', 'invoices': []}}, status=200)

        create_transaction('my-jwt-token', [{}], 'signer@test.com')

        assert responses.calls[0].request.headers['Authorization'] == 'Bearer my-jwt-token'

    @responses.activate
    def test_sends_payload(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        responses.post(url, json={'object': {'uuid': 'txn-123', 'invoices': []}}, status=200)

        payload = [{'invoiceFileB64': 'abc', 'invoiceTIEF': 'def'}]
        create_transaction('jwt', payload, 'signer@test.com')

        import json
        body = json.loads(responses.calls[0].request.body)
        assert body['invoices'] == payload
        assert body['signerEmail'] == 'signer@test.com'

    @responses.activate
    def test_returns_object(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        expected = {'uuid': 'txn-abc', 'invoices': [{'uuid': 'inv-1', 'status': 'CREATED'}]}
        responses.post(url, json={'object': expected}, status=200)

        result = create_transaction('jwt', [{}], 'signer@test.com')
        assert result == expected

    @responses.activate
    def test_raises_on_non_200(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        responses.post(url, json={'error': 'bad'}, status=400)

        with pytest.raises(NGSignAPIError, match='create_transaction failed'):
            create_transaction('jwt', [{}], 'signer@test.com')


class TestCheckInvoiceStatus:
    @responses.activate
    def test_correct_url(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/check/{uuid}'
        responses.post(url, json={'object': {'status': 'CREATED'}}, status=200)

        check_invoice_status('jwt', uuid)
        assert responses.calls[0].request.url == url

    @responses.activate
    def test_returns_object(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/check/{uuid}'
        expected = {'status': 'SIGNED', 'ttnReference': 'TTN-001'}
        responses.post(url, json={'object': expected}, status=200)

        result = check_invoice_status('jwt', uuid)
        assert result == expected

    @responses.activate
    def test_raises_on_non_200(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/check/{uuid}'
        responses.post(url, status=500)

        with pytest.raises(NGSignAPIError, match='check_invoice_status failed'):
            check_invoice_status('jwt', uuid)


class TestGetSignedXml:
    @responses.activate
    def test_decodes_base64(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/xml/{uuid}'
        xml_content = b'<TEIF>signed</TEIF>'
        b64 = base64.b64encode(xml_content).decode()
        responses.get(url, json={'object': b64}, status=200)

        result = get_signed_xml('jwt', uuid)
        assert result == xml_content

    @responses.activate
    def test_raises_on_non_200(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/xml/{uuid}'
        responses.get(url, status=404)

        with pytest.raises(NGSignAPIError, match='get_signed_xml failed'):
            get_signed_xml('jwt', uuid)


class TestGetPdsUrl:
    def test_format(self):
        result = get_pds_url('txn-abc-123')
        assert result == f'{PDS_BASE}/txn-abc-123'


class TestCreateOrg:
    @responses.activate
    def test_correct_url_and_payload(self):
        url = f'{PARTNER_API_BASE}/protected/user/partner/create'
        responses.post(url, json={'object': {'uuid': 'org-1', 'jwt': 'new-jwt'}}, status=200)

        result = create_org('partner-jwt', 'My Org', '123 Street', 'org@test.com')

        import json
        body = json.loads(responses.calls[0].request.body)
        assert body['name'] == 'My Org'
        assert body['street'] == '123 Street'
        assert body['country'] == 'TN'
        assert body['partnerUser']['email'] == 'org@test.com'
        assert result == {'uuid': 'org-1', 'jwt': 'new-jwt'}

    @responses.activate
    def test_raises_on_non_200(self):
        url = f'{PARTNER_API_BASE}/protected/user/partner/create'
        responses.post(url, status=500)

        with pytest.raises(NGSignAPIError, match='create_org failed'):
            create_org('partner-jwt', 'Org', 'Addr', 'e@t.com')


class TestUpdateOrg:
    @responses.activate
    def test_correct_url_and_payload(self):
        url = f'{PARTNER_API_BASE}/protected/user/partner/update'
        responses.post(url, json={'object': {'uuid': 'org-1', 'jwt': 'upd-jwt'}}, status=200)

        result = update_org('partner-jwt', 'old-jwt', 'Updated Org', '456 Ave', 'u@t.com')

        import json
        body = json.loads(responses.calls[0].request.body)
        assert body['jwt'] == 'old-jwt'
        assert body['name'] == 'Updated Org'
        assert result == {'uuid': 'org-1', 'jwt': 'upd-jwt'}


class TestRefreshJwt:
    @responses.activate
    def test_returns_new_jwt(self):
        uuid = 'org-uuid-1'
        url = f'{PARTNER_API_BASE}/protected/user/partner/refresh/{uuid}'
        responses.post(url, json={'object': {'jwt': 'refreshed-jwt'}}, status=200)

        result = refresh_jwt('partner-jwt', uuid)
        assert result == 'refreshed-jwt'

    @responses.activate
    def test_raises_on_non_200(self):
        uuid = 'org-uuid-1'
        url = f'{PARTNER_API_BASE}/protected/user/partner/refresh/{uuid}'
        responses.post(url, status=401)

        with pytest.raises(NGSignAuthError, match='refresh_jwt failed'):
            refresh_jwt('partner-jwt', uuid)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd "invoice app service" && python -m pytest tests/gov/test_ngsign_client.py -v`
Expected: All 14 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gov/test_ngsign_client.py
git commit -m "test: add NGSign client HTTP-level tests"
```

---

### Task 3: NGSign Service Layer Tests

**Files:**
- Create: `tests/gov/test_ngsign_service.py`

**Context:** The service layer (`invoice/gov/ngsign/service.py`) has three functions:
- `_get_account()` — switches to public schema to load `NGSignClientAccount`, restores tenant schema
- `submit_invoice(gov_invoice)` — builds payload via serializer, calls `client.create_transaction`, stores UUIDs
- `check_status(gov_invoice)` — calls `client.check_invoice_status`, fetches signed XML if terminal status

All `client.*` functions are mocked with `unittest.mock.patch`. The `_get_account` test needs a real tenant + `NGSignClientAccount` via fixtures.

**Reference files:**
- `invoice/gov/ngsign/service.py` — the module under test
- `invoice/gov/ngsign/exceptions.py` — exception classes

- [ ] **Step 1: Write the tests**

```python
import pytest
from unittest.mock import patch, MagicMock
from gov.ngsign.exceptions import (
    NGSignNotConfiguredError, NGSignAPIError, NGSignSubmissionError
)


@pytest.mark.django_db(transaction=True)
class TestSubmitInvoice:
    def test_calls_build_payload_and_create_transaction(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        fake_txn = {
            'uuid': 'txn-uuid-1',
            'invoices': [{'uuid': 'inv-uuid-1', 'status': 'CREATED'}],
        }

        with patch('gov.ngsign.service.serializer.build_payload', return_value={'payload': 'data'}) as mock_payload, \
             patch('gov.ngsign.service.client.create_transaction', return_value=fake_txn) as mock_create:
            from gov.ngsign.service import submit_invoice
            submit_invoice(gov_invoice)

            mock_payload.assert_called_once_with(gov_invoice)
            mock_create.assert_called_once_with(
                ngsign_account.org_jwt,
                [{'payload': 'data'}],
                signer_email=ngsign_account.signer_email,
            )

    def test_stores_transaction_and_invoice_uuids(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        fake_txn = {
            'uuid': 'txn-uuid-42',
            'invoices': [{'uuid': 'inv-uuid-42', 'status': 'CREATED'}],
        }

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}), \
             patch('gov.ngsign.service.client.create_transaction', return_value=fake_txn):
            from gov.ngsign.service import submit_invoice
            submit_invoice(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_transaction_uuid == 'txn-uuid-42'
        assert gov_invoice.ngsign_invoice_uuid == 'inv-uuid-42'

    def test_sets_status_from_response(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        fake_txn = {
            'uuid': 'txn-1',
            'invoices': [{'uuid': 'inv-1', 'status': 'CONFIGURED'}],
        }

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}), \
             patch('gov.ngsign.service.client.create_transaction', return_value=fake_txn):
            from gov.ngsign.service import submit_invoice
            submit_invoice(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'CONFIGURED'

    def test_defaults_to_created_when_status_absent(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        fake_txn = {
            'uuid': 'txn-1',
            'invoices': [{'uuid': 'inv-1'}],  # no 'status' key
        }

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}), \
             patch('gov.ngsign.service.client.create_transaction', return_value=fake_txn):
            from gov.ngsign.service import submit_invoice
            submit_invoice(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'CREATED'

    def test_raises_not_configured_when_no_account(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        from gov.ngsign.service import submit_invoice
        with pytest.raises(NGSignNotConfiguredError):
            submit_invoice(gov_invoice)

    def test_raises_not_configured_when_no_signer_email(self, tenant, seller, ngsign_account):
        ngsign_account.signer_email = ''
        ngsign_account.save()

        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}):
            from gov.ngsign.service import submit_invoice
            with pytest.raises(NGSignNotConfiguredError, match='signer_email'):
                submit_invoice(gov_invoice)

    def test_raises_not_configured_when_account_error(self, tenant, seller, ngsign_account):
        ngsign_account.status = 'ERROR'
        ngsign_account.save()

        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        from gov.ngsign.service import submit_invoice
        with pytest.raises(NGSignNotConfiguredError):
            submit_invoice(gov_invoice)

    def test_sets_error_on_api_failure(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory()

        with patch('gov.ngsign.service.serializer.build_payload', return_value={}), \
             patch('gov.ngsign.service.client.create_transaction', side_effect=NGSignAPIError('API down')):
            from gov.ngsign.service import submit_invoice
            with pytest.raises(NGSignSubmissionError):
                submit_invoice(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'ERROR'


@pytest.mark.django_db(transaction=True)
class TestCheckStatus:
    def test_updates_ngsign_status(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            ngsign_status='CREATED',
            ngsign_invoice_uuid='inv-uuid-1',
        )

        with patch('gov.ngsign.service.client.check_invoice_status',
                   return_value={'status': 'SIGNED', 'ttnReference': ''}):
            from gov.ngsign.service import check_status
            check_status(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'SIGNED'

    def test_fetches_signed_xml_on_ttn_signed(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            ngsign_status='SIGNED',
            ngsign_invoice_uuid='inv-uuid-1',
        )

        with patch('gov.ngsign.service.client.check_invoice_status',
                   return_value={'status': 'TTN_SIGNED'}), \
             patch('gov.ngsign.service.client.get_signed_xml',
                   return_value=b'<signed-xml/>') as mock_get:
            from gov.ngsign.service import check_status
            check_status(gov_invoice)

        mock_get.assert_called_once()
        gov_invoice.refresh_from_db()
        assert bytes(gov_invoice.signed_xml) == b'<signed-xml/>'
        assert gov_invoice.status == 'signed'

    def test_fetches_signed_xml_on_ttn_transfered(self, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            ngsign_status='SIGNED',
            ngsign_invoice_uuid='inv-uuid-1',
        )

        with patch('gov.ngsign.service.client.check_invoice_status',
                   return_value={'status': 'TTN_TRANSFERED'}), \
             patch('gov.ngsign.service.client.get_signed_xml',
                   return_value=b'<signed/>'):
            from gov.ngsign.service import check_status
            check_status(gov_invoice)

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'TTN_TRANSFERED'

    def test_raises_not_configured_when_no_account(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_invoice_uuid='inv-1')

        from gov.ngsign.service import check_status
        with pytest.raises(NGSignNotConfiguredError):
            check_status(gov_invoice)


@pytest.mark.django_db(transaction=True)
class TestGetAccount:
    def test_returns_account_for_current_tenant(self, tenant, ngsign_account):
        from gov.ngsign.service import _get_account
        account = _get_account()
        assert account is not None
        assert account.id == ngsign_account.id

    def test_returns_none_when_no_account(self, tenant):
        from gov.ngsign.service import _get_account
        assert _get_account() is None
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/gov/test_ngsign_service.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gov/test_ngsign_service.py
git commit -m "test: add NGSign service layer tests"
```

---

### Task 4: NGSign Serializer Tests

**Files:**
- Create: `tests/gov/test_ngsign_serializer.py`

**Context:** `serializer.build_payload()` in `invoice/gov/ngsign/serializer.py` builds the API payload for `create_transaction`. It base64-encodes the unsigned XML and a rendered PDF. The PDF rendering (`render_invoice_pdf`, `render_avoir_pdf`) uses WeasyPrint which requires system libs — we mock it to return dummy bytes. Everything else runs for real.

**Reference files:**
- `invoice/gov/ngsign/serializer.py` — the module under test

- [ ] **Step 1: Write the tests**

```python
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
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/gov/test_ngsign_serializer.py -v`
Expected: All 7 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gov/test_ngsign_serializer.py
git commit -m "test: add NGSign serializer tests"
```

---

### Task 5: TEIF Builder Tests

**Files:**
- Create: `tests/gov/test_teif_builder.py`

**Context:** The TEIF builder (`invoice/gov/teif/builder.py`) generates unsigned TEIF XML for invoices and credit notes. Tests parse the output XML with `lxml.etree` and verify structure, values, and edge cases. These need real model instances (via factories) including `InvoiceService` line items for invoice tests. No mocking needed.

**Reference files:**
- `invoice/gov/teif/builder.py` — module under test
- `invoice/gov/teif/namespaces.py` — `TEIF_NS = "urn:teif"`, `TEIF_VERSION = "1.8.9"`, `CONTROLLING_AGENCY = "TTN"`

- [ ] **Step 1: Write the tests**

```python
import pytest
from lxml import etree
from decimal import Decimal

TEIF_NS = 'urn:teif'


def _ns(tag):
    return f'{{{TEIF_NS}}}{tag}'


def _find(root, path):
    """Find element using TEIF namespace."""
    ns = {'t': TEIF_NS}
    return root.find(path, ns)


def _findall(root, path):
    ns = {'t': TEIF_NS}
    return root.findall(path, ns)


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
        ns = {'t': TEIF_NS}
        moas = root.findall('.//t:InvoiceMoa//t:Moa', ns)
        moa_map = {m.get('amountTypeCode'): m.find('t:Amount', ns).text for m in moas}

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
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory(uniqueId='')

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

        ns = {'t': TEIF_NS}
        moas = root.findall('.//t:InvoiceMoa//t:Moa', ns)
        timbre = [m for m in moas if m.get('amountTypeCode') == 'I-179']
        assert len(timbre) == 1
        assert timbre[0].find('t:Amount', ns).text == '0.000'

    def test_raises_valueerror_no_client(self, tenant, seller):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory(client=None)

        from gov.teif.builder import build_unsigned_teif_avoir
        with pytest.raises(ValueError, match='client'):
            build_unsigned_teif_avoir(cn, seller)

    def test_raises_valueerror_no_unique_id(self, tenant, seller):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory(uniqueId='')

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
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/gov/test_teif_builder.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gov/test_teif_builder.py
git commit -m "test: add TEIF XML builder tests"
```

---

### Task 6: Async Submission & Check View Tests

**Files:**
- Create: `tests/gov/test_async_submission.py`

**Context:** Tests for the async submit views (`invoice_ngsign_submit`, `avoir_ngsign_submit`), the background thread function (`_process_ngsign_submission`), and the check views (`invoice_ngsign_check`, `avoir_ngsign_check`). Submit views are tested via Django test client. The thread function is called directly (synchronously) with mocked dependencies. Check views mock `gov.ngsign.service.check_status`.

**URL patterns (from `invoice/sales/urls.py`):**
- `invoices/<int:invoice_id>/ngsign/submit/` → name `invoice-ngsign-submit`
- `invoices/<int:invoice_id>/ngsign/check/` → name `invoice-ngsign-check`
- `avoirs/<int:avoir_id>/ngsign/submit/` → name `avoir-ngsign-submit`
- `avoirs/<int:avoir_id>/ngsign/check/` → name `avoir-ngsign-check`

**Reference files:**
- `invoice/sales/views.py:2592-2868` — views and thread function

- [ ] **Step 1: Write the tests**

```python
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestInvoiceNgsignSubmit:
    def test_creates_gov_invoice_with_submitting_status(self, logged_in_client, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        with patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()
            url = reverse('invoice-ngsign-submit', args=[invoice.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True

        from gov.models import GovInvoice
        gov = GovInvoice.objects.get(invoice=invoice)
        assert gov.ngsign_status == 'SUBMITTING'
        assert gov.submitted_at is not None

    def test_duplicate_returns_409(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_status='SUBMITTING')

        url = reverse('invoice-ngsign-submit', args=[gov_invoice.invoice.id])
        resp = logged_in_client.post(url)

        assert resp.status_code == 409
        assert resp.json()['success'] is False

    def test_resets_non_submitting_status(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_status='ERROR', notes='old error')

        with patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()
            url = reverse('invoice-ngsign-submit', args=[gov_invoice.invoice.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'SUBMITTING'
        assert gov_invoice.notes == ''

    def test_nonexistent_returns_404(self, logged_in_client, tenant):
        url = reverse('invoice-ngsign-submit', args=[99999])
        resp = logged_in_client.post(url)
        assert resp.status_code == 404

    def test_spawns_thread(self, logged_in_client, tenant, seller):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        with patch('threading.Thread') as mock_thread:
            mock_instance = MagicMock()
            mock_thread.return_value = mock_instance
            url = reverse('invoice-ngsign-submit', args=[invoice.id])
            logged_in_client.post(url)

        mock_thread.assert_called_once()
        mock_instance.start.assert_called_once()

    def test_requires_login(self, tenant):
        from django.test import Client
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        anon_client = Client()
        url = reverse('invoice-ngsign-submit', args=[invoice.id])
        resp = anon_client.post(url)
        assert resp.status_code == 302

    def test_requires_post(self, logged_in_client, tenant):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        url = reverse('invoice-ngsign-submit', args=[invoice.id])
        resp = logged_in_client.get(url)
        assert resp.status_code == 405


@pytest.mark.django_db(transaction=True)
class TestAvoirNgsignSubmit:
    def test_creates_gov_invoice(self, logged_in_client, tenant, seller):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory()

        with patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()
            url = reverse('avoir-ngsign-submit', args=[cn.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        from gov.models import GovInvoice
        gov = GovInvoice.objects.get(credit_note=cn)
        assert gov.ngsign_status == 'SUBMITTING'

    def test_duplicate_returns_409(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(use_credit_note=True, ngsign_status='SUBMITTING')

        url = reverse('avoir-ngsign-submit', args=[gov_invoice.credit_note.id])
        resp = logged_in_client.post(url)
        assert resp.status_code == 409


@pytest.mark.django_db(transaction=True)
class TestProcessNgsignSubmission:
    def test_sets_error_on_exception(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_status='SUBMITTING')

        # Don't mock set_schema — the function needs it to access the tenant DB.
        # Only mock connection.close to prevent closing the test's connection.
        with patch('gov.ngsign.service.submit_invoice', side_effect=Exception('API failure')), \
             patch('django.db.connection.close'):
            from sales.views import _process_ngsign_submission
            _process_ngsign_submission(gov_invoice.id, 'test_tenant')

        gov_invoice.refresh_from_db()
        assert gov_invoice.ngsign_status == 'ERROR'
        assert 'API failure' in gov_invoice.notes

    def test_closes_connection(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(ngsign_status='SUBMITTING')

        with patch('gov.ngsign.service.submit_invoice'), \
             patch('django.db.connection.close') as mock_close:
            from sales.views import _process_ngsign_submission
            _process_ngsign_submission(gov_invoice.id, 'test_tenant')

        mock_close.assert_called_once()

    def test_generates_xml_for_invoice(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(unsigned_xml=b'', ngsign_status='SUBMITTING')

        with patch('gov.ngsign.service.submit_invoice'), \
             patch('gov.teif.builder.build_unsigned_teif', return_value=b'<TEIF>gen</TEIF>') as mock_build, \
             patch('django.db.connection.close'):
            from sales.views import _process_ngsign_submission
            _process_ngsign_submission(gov_invoice.id, 'test_tenant')

        mock_build.assert_called_once()

    def test_generates_xml_for_avoir(self, tenant, seller):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            use_credit_note=True, unsigned_xml=b'', ngsign_status='SUBMITTING'
        )

        with patch('gov.ngsign.service.submit_invoice'), \
             patch('gov.teif.builder.build_unsigned_teif_avoir', return_value=b'<TEIF>av</TEIF>') as mock_build, \
             patch('django.db.connection.close'):
            from sales.views import _process_ngsign_submission
            _process_ngsign_submission(gov_invoice.id, 'test_tenant')

        mock_build.assert_called_once()


@pytest.mark.django_db(transaction=True)
class TestInvoiceNgsignCheck:
    def test_returns_status_on_success(self, logged_in_client, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            ngsign_status='CREATED', ngsign_invoice_uuid='inv-uuid-1'
        )

        with patch('gov.ngsign.service.check_status',
                   return_value={'status': 'SIGNED', 'ttnReference': 'TTN-001'}):
            url = reverse('invoice-ngsign-check', args=[gov_invoice.invoice.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert 'ngsign_status' in data

    def test_not_submitted_returns_400(self, logged_in_client, tenant):
        from tests.factories import InvoiceFactory
        invoice = InvoiceFactory()

        url = reverse('invoice-ngsign-check', args=[invoice.id])
        resp = logged_in_client.post(url)
        assert resp.status_code == 400

    def test_api_error_returns_500(self, logged_in_client, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        from gov.ngsign.exceptions import NGSignAPIError
        gov_invoice = GovInvoiceFactory(
            ngsign_status='CREATED', ngsign_invoice_uuid='inv-uuid-1'
        )

        with patch('gov.ngsign.service.check_status', side_effect=NGSignAPIError('timeout')):
            url = reverse('invoice-ngsign-check', args=[gov_invoice.invoice.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 500


@pytest.mark.django_db(transaction=True)
class TestAvoirNgsignCheck:
    def test_returns_status(self, logged_in_client, tenant, seller, ngsign_account):
        from tests.factories import GovInvoiceFactory
        gov_invoice = GovInvoiceFactory(
            use_credit_note=True,
            ngsign_status='CREATED',
            ngsign_invoice_uuid='inv-uuid-1',
        )

        with patch('gov.ngsign.service.check_status',
                   return_value={'status': 'SIGNED', 'ttnReference': ''}):
            url = reverse('avoir-ngsign-check', args=[gov_invoice.credit_note.id])
            resp = logged_in_client.post(url)

        assert resp.status_code == 200
        assert resp.json()['success'] is True

    def test_not_submitted_returns_400(self, logged_in_client, tenant):
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory()

        url = reverse('avoir-ngsign-check', args=[cn.id])
        resp = logged_in_client.post(url)
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/gov/test_async_submission.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gov/test_async_submission.py
git commit -m "test: add async submission and check view tests"
```

---

### Task 7: Notification API Tests

**Files:**
- Create: `tests/gov/test_notification_api.py`

**Context:** Tests for `ngsign_pending_api` (`GET /api/ngsign/pending/`). This endpoint queries `GovInvoice` records, groups them by status, detects stale submissions (>60s in SUBMITTING), and returns JSON. Uses `freezegun` for time-dependent stale detection tests.

**URL pattern:** `api/ngsign/pending/` → name `ngsign-pending-api`

**Reference files:**
- `invoice/sales/views.py:2796-2867` — the view

- [ ] **Step 1: Write the tests**

```python
import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone


API_URL_NAME = 'ngsign-pending-api'


@pytest.mark.django_db(transaction=True)
class TestNgsignPendingApi:
    def test_empty_response(self, logged_in_client, tenant):
        url = reverse(API_URL_NAME)
        resp = logged_in_client.get(url)

        assert resp.status_code == 200
        data = resp.json()
        assert data == {'to_sign': [], 'errors': [], 'in_progress': [], 'total': 0}

    def test_groups_created_to_sign(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CREATED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        data = resp.json()
        assert len(data['to_sign']) == 1
        assert data['to_sign'][0]['status'] == 'CREATED'

    def test_groups_configured_to_sign(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CONFIGURED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['to_sign']) == 1

    def test_groups_error_to_errors(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='ERROR')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['errors']) == 1

    def test_groups_ttn_rejected_to_errors(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='TTN_REJECTED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['errors']) == 1

    def test_groups_ttn_nottransfered_to_errors(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='TTN_NOTTRANSFERED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['errors']) == 1

    def test_groups_fresh_submitting_to_in_progress(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='SUBMITTING', submitted_at=timezone.now())

        resp = logged_in_client.get(reverse(API_URL_NAME))
        data = resp.json()
        assert len(data['in_progress']) == 1
        assert data['in_progress'][0]['status'] == 'SUBMITTING'

    def test_groups_signed_to_in_progress(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='SIGNED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert len(resp.json()['in_progress']) == 1

    def test_excludes_ttn_signed(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='TTN_SIGNED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert resp.json()['total'] == 0

    def test_excludes_ttn_transfered(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='TTN_TRANSFERED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert resp.json()['total'] == 0

    def test_excludes_cancelled(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CANCELLED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        assert resp.json()['total'] == 0

    def test_stale_submitting_promoted_to_error(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        stale_time = timezone.now() - timedelta(seconds=120)
        gov = GovInvoiceFactory(ngsign_status='SUBMITTING', submitted_at=stale_time)

        resp = logged_in_client.get(reverse(API_URL_NAME))
        data = resp.json()
        assert len(data['errors']) == 1
        assert data['errors'][0]['status'] == 'ERROR'

        # Verify DB was updated
        gov.refresh_from_db()
        assert gov.ngsign_status == 'ERROR'
        assert 'expirée' in gov.notes

    def test_response_fields_for_invoice(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory, InvoiceFactory, ClientFactory
        client = ClientFactory(clientname='ACME Corp')
        invoice = InvoiceFactory(client=client, uniqueId='FA-042-2026')
        gov = GovInvoiceFactory(
            invoice=invoice,
            ngsign_status='CREATED',
            ngsign_transaction_uuid='txn-uuid-abc',
        )

        resp = logged_in_client.get(reverse(API_URL_NAME))
        item = resp.json()['to_sign'][0]

        assert item['doc_type'] == 'invoice'
        assert item['doc_number'] == 'FA-042-2026'
        assert item['client_name'] == 'ACME Corp'
        assert 'txn-uuid-abc' in item['pds_url']
        assert f'/invoices/{invoice.id}/' in item['detail_url']

    def test_response_fields_for_avoir(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory, CreditNoteFactory, ClientFactory
        client = ClientFactory(clientname='Beta LLC')
        cn = CreditNoteFactory(client=client, uniqueId='AV-007-2026')
        gov = GovInvoiceFactory(
            use_credit_note=True,
            credit_note=cn,
            ngsign_status='CREATED',
            ngsign_transaction_uuid='txn-uuid-def',
        )

        resp = logged_in_client.get(reverse(API_URL_NAME))
        item = resp.json()['to_sign'][0]

        assert item['doc_type'] == 'avoir'
        assert item['doc_number'] == 'AV-007-2026'
        assert item['client_name'] == 'Beta LLC'

    def test_pds_url_null_when_no_uuid(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CREATED', ngsign_transaction_uuid=None)

        resp = logged_in_client.get(reverse(API_URL_NAME))
        item = resp.json()['to_sign'][0]
        assert item['pds_url'] is None

    def test_total_count(self, logged_in_client, tenant, seller):
        from tests.factories import GovInvoiceFactory
        GovInvoiceFactory(ngsign_status='CREATED')
        GovInvoiceFactory(ngsign_status='ERROR')
        GovInvoiceFactory(ngsign_status='SIGNED')

        resp = logged_in_client.get(reverse(API_URL_NAME))
        data = resp.json()
        assert data['total'] == 3
        assert data['total'] == len(data['to_sign']) + len(data['errors']) + len(data['in_progress'])

    def test_requires_login(self, tenant):
        from django.test import Client
        anon = Client()
        resp = anon.get(reverse(API_URL_NAME))
        assert resp.status_code == 302

    def test_rejects_post(self, logged_in_client, tenant):
        resp = logged_in_client.post(reverse(API_URL_NAME))
        assert resp.status_code == 405
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/gov/test_notification_api.py -v`
Expected: All 19 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gov/test_notification_api.py
git commit -m "test: add notification API endpoint tests"
```

---

### Task 8: Sales Model Tests (Phase 2 Start)

**Files:**
- Create: `tests/sales/test_models.py`

**Context:** Phase 2 begins — layer-based tests for existing app code. Start with the most critical business logic: invoice and credit note calculation methods. These methods compute subtotals, discounts, TVA (tax), and totals. They need `InvoiceService` line items to be meaningful.

**Reference files:**
- `invoice/sales/models.py:441-510` — Invoice calculation methods
- `invoice/sales/models.py:615-620` — CreditNote calculation methods

- [ ] **Step 1: Write the tests**

```python
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
```

- [ ] **Step 2: Run tests**

Run: `cd "invoice app service" && python -m pytest tests/sales/test_models.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/sales/test_models.py tests/sales/__init__.py tests/payment/__init__.py
git commit -m "test: add sales model calculation tests"
```

---

### Task 9: Run Full Suite & Coverage Report

**Files:** None (verification only)

- [ ] **Step 1: Run the entire test suite with coverage**

Run: `cd "invoice app service" && python -m pytest -v --tb=short`
Expected: All tests PASS, coverage report printed

- [ ] **Step 2: Review coverage output**

Look at the `--cov-report=term-missing` output. Note which lines in `gov/`, `sales/`, `payment/` are covered vs missing. The NGSign-related files should have high coverage. `sales/views.py` will still have low overall coverage since we only tested the NGSign views.

- [ ] **Step 3: Commit any fixes needed**

If any tests need adjustments, fix and commit.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: complete test suite — full NGSign coverage + sales model tests"
```
