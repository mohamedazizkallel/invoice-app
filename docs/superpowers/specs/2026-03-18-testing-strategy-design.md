# Testing Strategy Design

**Date:** 2026-03-18
**Status:** Draft
**Branch:** feature/ngsign-integration

## Problem

The project has zero test coverage. All three test files (`sales/tests.py`, `gov/tests.py`, `payment/tests.py`) are empty stubs. There are no test dependencies, no test configuration, no CI/CD, and no fixtures. The recently added async NGSign submission and notification bell features are untested, representing the highest-risk code in the codebase.

## Solution

Establish a complete testing infrastructure from scratch, then write tests in two phases:
1. **Phase 1 (priority):** Feature-based tests for the new NGSign integration (async submission, notification API, service layer, TEIF XML builder, NGSign client, serializer)
2. **Phase 2:** Layer-based tests for the broader app (models, views, forms across sales and payment)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Test runner | pytest + pytest-django | Industry standard, better output, fixtures via conftest, powerful selection |
| Database | Real PostgreSQL | App uses django-tenants which requires PostgreSQL; avoids false positives from engine differences |
| Coverage | pytest-cov | Track progress from zero, identify gaps, minimal setup cost |
| Test data | factory-boy | Complex models (Invoice has many fields/relations); factories provide one-line creation with overrides |
| HTTP mocking | `responses` for client-level tests, `unittest.mock.patch` for service/view-level tests | Client tests verify URL construction and HTTP handling; higher layers mock at the client boundary |
| Time mocking | freezegun | Required for stale detection tests (60-second threshold) |
| Test organization | Hybrid | Feature-based for NGSign (cuts across layers), layer-based for broader app |

---

## 1. Test Infrastructure

### Dependencies

New file `requirements-dev.txt`:

```
-r requirements.txt
pytest==8.3.5
pytest-django==4.9.0
pytest-cov==6.1.1
factory-boy==3.3.3
responses==0.25.7
freezegun==1.4.0
```

### Configuration

`pytest.ini` at project root (`invoice app service/`):

```ini
[pytest]
DJANGO_SETTINGS_MODULE = invoice.settings
pythonpath = invoice
testpaths = tests
addopts = --cov=invoice/gov --cov=invoice/sales --cov=invoice/payment --cov-report=term-missing --tb=short
```

Note: `--cov` paths are relative to the project root (filesystem paths), not Python package names. Since `pythonpath = invoice`, the import names are `gov`, `sales`, `payment`, but coverage must point to the actual directories.

### Directory Structure

```
tests/
  __init__.py
  conftest.py                    # shared fixtures: tenant, user, logged_in_client, settings
  factories.py                   # all factory-boy factories
  gov/
    __init__.py
    test_async_submission.py     # async submit views + thread function + check views
    test_notification_api.py     # ngsign_pending_api endpoint
    test_ngsign_client.py        # NGSign client module (HTTP-level tests)
    test_ngsign_service.py       # service layer (submit, check_status)
    test_ngsign_serializer.py    # serializer.build_payload
    test_teif_builder.py         # TEIF XML generation
  sales/
    __init__.py
    test_models.py               # Invoice/CreditNote business logic
    test_views.py                # CRUD views
    test_forms.py                # form validation
  payment/
    __init__.py
    test_models.py               # payment model logic
```

### Multi-Tenant Test Setup

The `conftest.py` provides shared fixtures for tenant schema setup:

```python
import pytest
from unittest.mock import patch
from django.db import connection

@pytest.fixture(scope='session')
def tenant_setup(django_db_setup, django_db_blocker):
    """Create a test tenant and switch to its schema."""
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
    """Create a Settings (seller) instance — needed by most NGSign code paths.
    Mocks _sync_ngsign_org to prevent real API calls on Settings.save()."""
    from tests.factories import SettingsFactory
    with patch('sales.models._sync_ngsign_org'):
        return SettingsFactory()

@pytest.fixture
def ngsign_account(tenant_setup, db):
    """Create an NGSignClientAccount in the public schema for the test tenant."""
    from django.db import connection
    current = connection.schema_name
    connection.set_schema_to_public()
    from tests.factories import NGSignClientAccountFactory
    account = NGSignClientAccountFactory(tenant=tenant_setup)
    connection.set_schema(current)
    return account
```

**Test data cleanup:** All DB-hitting tests use `@pytest.mark.django_db(transaction=True)` since django-tenants needs real transactions for schema switching. Each test that creates tenant-schema data should use function-scoped fixtures so data is created fresh per test. The session-scoped `tenant_setup` only creates the tenant/schema once; tenant-schema data (invoices, gov_invoices, etc.) is created per test and cleaned up by transaction rollback.

**Public vs. tenant schema:** `NGSignClientAccount` and `Tenant` live in the **public** schema. The `ngsign_account` fixture explicitly switches to public before creating the account, then restores the tenant schema. All other factories (Client, Invoice, etc.) create data in the current tenant schema.

---

## 2. Test Data Factories

Single file `tests/factories.py` with factory-boy classes:

```python
import factory
from factory.django import DjangoModelFactory
from django.utils import timezone

class ClientFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Client'

    clientname = factory.Sequence(lambda n: f'Client {n}')
    mf = factory.Sequence(lambda n: f'1234567A/B/M/{n:03d}')
    adress = factory.Faker('address')
    emailAddress = factory.LazyAttribute(lambda o: f'{o.clientname.lower().replace(" ", "")}@test.com')

class ServiceFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Service'

    title = factory.Sequence(lambda n: f'Service {n}')
    description = factory.Faker('sentence')
    billing_type = 'flat'
    price = factory.Faker('pydecimal', left_digits=3, right_digits=3, positive=True)

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
    unit_price = factory.Faker('pydecimal', left_digits=3, right_digits=3, positive=True)
    hours_used = None
    days_used = None
    units_used = None
    has_fodec = False

class CreditNoteFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.CreditNote'

    client = factory.SubFactory(ClientFactory)
    uniqueId = factory.Sequence(lambda n: f'AV-{n:03d}-2026')
    # date_created uses auto_now_add=True on the model, so it cannot be overridden via factory
    description = factory.Faker('sentence')
    amount_ht = factory.Faker('pydecimal', left_digits=3, right_digits=3, positive=True)
    tva = 19

class SettingsFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Settings'

    clientname = 'Test Company SARL'
    mf = '9876543X/Y/Z/000'
    adress = '123 Rue Test, Tunis'

class GovInvoiceFactory(DjangoModelFactory):
    class Meta:
        model = 'gov.GovInvoice'
        exclude = ['use_credit_note']

    use_credit_note = False  # Control flag, not a model field

    invoice = factory.Maybe('use_credit_note', yes_declaration=None, no_declaration=factory.SubFactory(InvoiceFactory))
    credit_note = factory.Maybe('use_credit_note', yes_declaration=factory.SubFactory(CreditNoteFactory), no_declaration=None)
    unsigned_xml = b'<TEIF>test</TEIF>'
    status = 'draft'
    ngsign_status = None

class NGSignClientAccountFactory(DjangoModelFactory):
    class Meta:
        model = 'tenants.NGSignClientAccount'

    # tenant must be provided explicitly (lives in public schema)
    org_uuid = factory.Faker('uuid4')
    org_jwt = factory.Faker('sha256')
    signer_email = 'signer@test.com'
    status = 'ACTIVE'
```

**Usage notes:**
- `GovInvoiceFactory()` creates an invoice-linked GovInvoice by default.
- `GovInvoiceFactory(use_credit_note=True)` creates a credit-note-linked GovInvoice.
- `NGSignClientAccountFactory(tenant=tenant)` — the `tenant` must be passed explicitly since it lives in the public schema.
- `InvoiceServiceFactory(invoice=my_invoice)` — use to add line items to an existing invoice for TEIF builder tests.
- When reading `unsigned_xml` back from PostgreSQL, it returns `memoryview`, not `bytes`. Use `bytes(gov_invoice.unsigned_xml)` for comparisons, matching what the production code does.

---

## 3. Phase 1: NGSign Feature Tests

### test_async_submission.py

Tests for `invoice_ngsign_submit`, `avoir_ngsign_submit`, `_process_ngsign_submission`, `invoice_ngsign_check`, and `avoir_ngsign_check`:

**Submit views:**

| Test | What it verifies |
|------|-----------------|
| `test_submit_creates_gov_invoice_with_submitting_status` | POST creates GovInvoice with `ngsign_status='SUBMITTING'` and `submitted_at` set, returns 200 with success JSON |
| `test_submit_duplicate_returns_409` | POST while existing GovInvoice has `SUBMITTING` status returns 409 |
| `test_submit_resets_any_non_submitting_status` | POST when existing GovInvoice has any non-SUBMITTING status (ERROR, CREATED, etc.) resets to `SUBMITTING`, clears notes. The guard only blocks `SUBMITTING`. |
| `test_submit_nonexistent_invoice_returns_404` | POST with invalid invoice ID returns 404 (view is `@require_POST`, so must use POST) |
| `test_submit_spawns_thread` | Mock `threading.Thread` to verify it's called with correct args and `.start()` is called |
| `test_thread_sets_error_on_exception` | Call `_process_ngsign_submission` directly with mocked service that raises; verify `ngsign_status='ERROR'` and `notes` populated (truncated to 500 chars) |
| `test_thread_closes_connection` | Call `_process_ngsign_submission` with mock; verify `connection.close()` called in all cases (success and error) |
| `test_thread_generates_xml_for_invoice` | Call with GovInvoice (invoice FK) that has empty `unsigned_xml`; verify `build_unsigned_teif` is called |
| `test_thread_generates_xml_for_avoir` | Call with GovInvoice (credit_note FK) that has empty `unsigned_xml`; verify `build_unsigned_teif_avoir` is called |
| `test_avoir_submit_creates_gov_invoice` | Same as invoice submit but for credit note FK |
| `test_avoir_submit_duplicate_returns_409` | Same guard logic for avoirs |
| `test_requires_login` | Anonymous POST returns 302 redirect |
| `test_requires_post` | GET returns 405 |

**Check views:**

| Test | What it verifies |
|------|-----------------|
| `test_check_returns_status_on_success` | POST to check view returns 200 with `ngsign_status` and `ttn_reference` |
| `test_check_not_submitted_returns_400` | Invoice has no GovInvoice or no `ngsign_invoice_uuid` → returns 400 |
| `test_check_api_error_returns_500` | `check_status` raises `NGSignAPIError` → returns 500 with error message |
| `test_avoir_check_returns_status` | Same check flow for avoirs |
| `test_avoir_check_not_submitted_returns_400` | Same 400 for avoirs |
| `test_check_requires_login` | Anonymous returns 302 |
| `test_check_requires_post` | GET returns 405 |

**Mocking strategy:** The thread function is tested directly (not via actual threading) by calling `_process_ngsign_submission()` synchronously. The NGSign service calls (`submit_invoice`, `check_status`) are mocked using `unittest.mock.patch`. The submit views mock `threading.Thread` to verify spawning without actually running the thread.

### test_notification_api.py

Tests for `ngsign_pending_api`:

| Test | What it verifies |
|------|-----------------|
| `test_empty_response_when_no_documents` | Returns `{"to_sign": [], "errors": [], "in_progress": [], "total": 0}` |
| `test_groups_created_to_sign` | GovInvoice with `CREATED` appears in `to_sign` |
| `test_groups_configured_to_sign` | GovInvoice with `CONFIGURED` appears in `to_sign` |
| `test_groups_error_to_errors` | GovInvoice with `ERROR` appears in `errors` |
| `test_groups_ttn_rejected_to_errors` | GovInvoice with `TTN_REJECTED` appears in `errors` |
| `test_groups_ttn_nottransfered_to_errors` | GovInvoice with `TTN_NOTTRANSFERED` appears in `errors` |
| `test_groups_submitting_to_in_progress` | GovInvoice with `SUBMITTING` (fresh) appears in `in_progress` |
| `test_groups_signed_to_in_progress` | GovInvoice with `SIGNED` appears in `in_progress` |
| `test_excludes_terminal_ttn_signed` | GovInvoice with `TTN_SIGNED` not in response |
| `test_excludes_terminal_ttn_transfered` | GovInvoice with `TTN_TRANSFERED` not in response |
| `test_excludes_terminal_cancelled` | GovInvoice with `CANCELLED` not in response |
| `test_stale_submitting_promoted_to_error` | GovInvoice with `SUBMITTING` and `submitted_at` >60s ago appears in `errors`, DB updated with timeout note |
| `test_fresh_submitting_stays_in_progress` | GovInvoice with `SUBMITTING` and `submitted_at` <60s ago stays in `in_progress` |
| `test_response_fields_for_invoice` | Verify `doc_type`, `doc_number`, `client_name`, `pds_url`, `detail_url` correct for invoice |
| `test_response_fields_for_avoir` | Same for credit note |
| `test_pds_url_null_when_no_uuid` | `pds_url` is `null` when `ngsign_transaction_uuid` is None |
| `test_total_count_correct` | `total` equals sum of all groups |
| `test_requires_login` | Anonymous GET returns 302 |
| `test_rejects_post` | POST returns 405 |

**Time mocking:** Stale detection tests use `freezegun` to freeze `timezone.now()` so the 60-second threshold is deterministic.

### test_ngsign_client.py

Tests for the NGSign client module (`gov/ngsign/client.py`), using the `responses` library to mock HTTP calls:

| Test | What it verifies |
|------|-----------------|
| `test_create_transaction_posts_correct_url` | Sends POST to `/server/protected/invoice/xml/transaction/create` |
| `test_create_transaction_sends_auth_header` | `Authorization: Bearer {jwt}` header present |
| `test_create_transaction_sends_payload` | Request body contains `invoices` and `signerEmail` |
| `test_create_transaction_returns_object` | Returns `resp.json()['object']` on 200 |
| `test_create_transaction_raises_on_non_200` | Raises `NGSignAPIError` on 400/500 |
| `test_check_invoice_status_correct_url` | Sends POST to `/server/protected/invoice/xml/check/{uuid}` |
| `test_check_invoice_status_returns_object` | Returns `resp.json()['object']` on 200 |
| `test_check_invoice_status_raises_on_non_200` | Raises `NGSignAPIError` on error |
| `test_get_signed_xml_decodes_base64` | Returns `base64.b64decode(resp.json()['object'])` |
| `test_get_signed_xml_raises_on_non_200` | Raises `NGSignAPIError` on error |
| `test_get_pds_url_format` | Returns `https://sandbox.ng-sign.com/pds/#/teif/invoice/{uuid}` |
| `test_create_org_correct_url_and_payload` | POST to `/protected/user/partner/create` with org details |
| `test_update_org_correct_url_and_payload` | POST to `/protected/user/partner/update` with org details + jwt |
| `test_refresh_jwt_returns_new_jwt` | Returns `resp.json()['object']['jwt']` |

**Mocking strategy:** Uses `@responses.activate` decorator to intercept `requests.post/get` calls. No real HTTP calls made. Tests verify URL construction, header formatting, payload structure, response parsing, and error handling.

### test_ngsign_service.py

Tests for `submit_invoice`, `check_status`, `_get_account`:

| Test | What it verifies |
|------|-----------------|
| `test_submit_calls_build_payload_and_create_transaction` | Mocks both, verifies called with correct args |
| `test_submit_stores_transaction_and_invoice_uuids` | After submit, GovInvoice has correct UUIDs |
| `test_submit_sets_status_from_response` | After submit, `ngsign_status` is read from API response (`invoice_info.get('status', 'CREATED')`). Mock must return response dict with `invoices: [{uuid: ..., status: 'CREATED'}]`. Also test the default when `status` key is absent. |
| `test_submit_raises_not_configured_when_no_account` | No NGSignClientAccount → raises `NGSignNotConfiguredError` |
| `test_submit_raises_not_configured_when_no_signer_email` | Account exists but `signer_email` empty → raises |
| `test_submit_raises_not_configured_when_account_error` | Account has `status='ERROR'` → raises |
| `test_submit_sets_error_on_api_failure` | Mock API to raise; verify `ngsign_status='ERROR'` |
| `test_check_status_updates_ngsign_status` | Mock API response; verify status updated on model |
| `test_check_status_fetches_signed_xml_on_ttn_signed` | When status is `TTN_SIGNED`, verify `get_signed_xml` called and stored |
| `test_check_status_fetches_signed_xml_on_ttn_transfered` | Same for `TTN_TRANSFERED` |
| `test_get_account_switches_schema` | Verify public schema switch and restore |

**Mocking strategy:** NGSign client functions (`client.create_transaction`, `client.check_invoice_status`, `client.get_signed_xml`) are mocked with `unittest.mock.patch`. The `_get_account` function is tested by creating tenant + NGSignClientAccount fixtures via `ngsign_account` conftest fixture.

### test_ngsign_serializer.py

Tests for `serializer.build_payload` (`gov/ngsign/serializer.py`):

| Test | What it verifies |
|------|-----------------|
| `test_build_payload_invoice_structure` | Returns dict with keys `invoiceFileB64`, `invoiceTIEF`, `invoiceNumber`, `clientEmail`, `configuration` |
| `test_build_payload_invoice_encodes_xml_b64` | `invoiceTIEF` is valid base64 of `unsigned_xml` |
| `test_build_payload_invoice_encodes_pdf_b64` | `invoiceFileB64` is valid base64 (mock `render_invoice_pdf`) |
| `test_build_payload_invoice_number` | `invoiceNumber` matches `invoice.uniqueId` |
| `test_build_payload_avoir_structure` | Same structure for credit notes |
| `test_build_payload_avoir_uses_credit_note_fields` | `invoiceNumber` matches `credit_note.uniqueId` |
| `test_build_payload_client_email_fallback` | `clientEmail` is empty string when client has no email |

**Mocking strategy:** Mock `render_invoice_pdf` and `render_avoir_pdf` (WeasyPrint PDF generation) to return dummy bytes. Everything else runs for real.

### test_teif_builder.py

Tests for `build_unsigned_teif`, `build_unsigned_teif_avoir`, and utility functions:

| Test | What it verifies |
|------|-----------------|
| `test_produces_valid_xml` | Output is parseable XML |
| `test_root_has_teif_namespace_and_version` | Root element is `TEIF` with correct namespace, version, controlingAgency |
| `test_sender_receiver_mf_stripped` | MF values have slashes removed |
| `test_bgm_has_correct_doc_type_invoice` | `DocumentType` code is `I-11` for invoices |
| `test_bgm_has_correct_doc_type_avoir` | `DocumentType` code is `I-12` for avoirs |
| `test_dtm_has_correct_date_format` | Date formatted as `ddMMyy` |
| `test_line_items_match_invoice_services` | Number of `Lin` elements matches services, amounts correct (requires `InvoiceServiceFactory`) |
| `test_totals_correct` | HT, TVA, timbre fiscal, TTC amounts match model calculations |
| `test_discount_section_present_when_discount` | `InvoiceAlc` present with correct amount when `discount > 0` |
| `test_discount_section_absent_when_no_discount` | `InvoiceAlc` absent when `discount == 0` |
| `test_avoir_has_single_line_item` | Credit note XML has exactly one `Lin` |
| `test_avoir_totals_no_timbre` | Timbre fiscal is `0.000` for avoirs |
| `test_raises_valueerror_no_client_invoice` | Invoice without client raises `ValueError` |
| `test_raises_valueerror_no_client_avoir` | Credit note without client raises `ValueError` |
| `test_raises_valueerror_no_unique_id_invoice` | Invoice without uniqueId raises `ValueError` |
| `test_raises_valueerror_no_unique_id_avoir` | Credit note without uniqueId raises `ValueError` |
| `test_raises_valueerror_no_mf_invoice` | Missing MF on seller or client raises `ValueError` |
| `test_raises_valueerror_no_mf_avoir` | Same for credit note |
| `test_sanitize_strips_forbidden_chars` | `_sanitize` removes `%`, `/`, `\`, `<`, `>`, `&`, `"`, `'` (includes backslash) |
| `test_condense_to_single_line` | Whitespace between tags removed, content preserved |

**No mocking needed:** These tests create real model instances via factories (including `InvoiceServiceFactory` for line items) and verify the generated XML by parsing it with `lxml.etree`.

---

## 4. Phase 2: Broad App Coverage

Lower priority, layer-based tests for the existing app.

**Note:** `Settings.save()` triggers `_sync_ngsign_org` via `on_commit`, which makes NGSign API calls. All tests that create or modify `Settings` must mock `_sync_ngsign_org` to avoid real API calls.

### tests/sales/test_models.py

- `Invoice.calculate_service_subtotal()` — correct sum of line items
- `Invoice.calculate_discount_amount()` — percentage-based discount calculation
- `Invoice.calculate_subtotal_after_discount()` — subtotal minus discount
- `Invoice.calculate_tva_amount()` — TVA on subtotal after discount
- `Invoice.calculate_total()` — subtotal + TVA + timbre fiscal
- `Invoice.get_tva()` — returns TVA rate
- `Invoice.get_timbre_fiscal()` — returns timbre amount
- `CreditNote.calculate_tva_amount()` — TVA on credit note amount
- `CreditNote.calculate_total()` — amount_ht + TVA
- `Settings.get_cached()` — returns cached instance, invalidates on change
- Edge cases: zero amounts, 100% discount, missing services

### tests/sales/test_views.py

- Dashboard loads with correct context (invoice stats, recent invoices)
- Invoice list with pagination
- Invoice create with valid form data
- Invoice edit updates fields
- Invoice delete with protection check
- Login required on all protected views
- Login/logout flow

### tests/sales/test_forms.py

- `ClientForm` — valid data accepted, required fields enforced
- `InvoiceForm` — valid data accepted, validates line items
- `SettingsForm` — valid data accepted, MF format validated

### tests/payment/test_models.py

- `Retenu` and `PurchaseRetenu` model logic (if calculation methods exist)

---

## 5. Files Modified/Created

| File | Changes |
|------|---------|
| `requirements-dev.txt` | **Create**: dev dependencies including test libraries |
| `pytest.ini` | **Create**: pytest configuration |
| `tests/__init__.py` | **Create**: package init |
| `tests/conftest.py` | **Create**: shared fixtures (tenant, user, client, seller, ngsign_account) |
| `tests/factories.py` | **Create**: factory-boy factory classes |
| `tests/gov/__init__.py` | **Create**: package init |
| `tests/gov/test_async_submission.py` | **Create**: async submit + thread + check view tests |
| `tests/gov/test_notification_api.py` | **Create**: pending API endpoint tests |
| `tests/gov/test_ngsign_client.py` | **Create**: NGSign client HTTP-level tests |
| `tests/gov/test_ngsign_service.py` | **Create**: service layer tests |
| `tests/gov/test_ngsign_serializer.py` | **Create**: serializer.build_payload tests |
| `tests/gov/test_teif_builder.py` | **Create**: TEIF XML builder tests |
| `tests/sales/__init__.py` | **Create**: package init |
| `tests/sales/test_models.py` | **Create**: model business logic tests |
| `tests/sales/test_views.py` | **Create**: CRUD view tests |
| `tests/sales/test_forms.py` | **Create**: form validation tests |
| `tests/payment/__init__.py` | **Create**: package init |
| `tests/payment/test_models.py` | **Create**: payment model tests |

No changes to existing production code. No new production dependencies.
