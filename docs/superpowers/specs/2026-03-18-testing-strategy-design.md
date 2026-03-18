# Testing Strategy Design

**Date:** 2026-03-18
**Status:** Draft
**Branch:** feature/ngsign-integration

## Problem

The project has zero test coverage. All three test files (`sales/tests.py`, `gov/tests.py`, `payment/tests.py`) are empty stubs. There are no test dependencies, no test configuration, no CI/CD, and no fixtures. The recently added async NGSign submission and notification bell features are untested, representing the highest-risk code in the codebase.

## Solution

Establish a complete testing infrastructure from scratch, then write tests in two phases:
1. **Phase 1 (priority):** Feature-based tests for the new NGSign integration (async submission, notification API, service layer, TEIF XML builder)
2. **Phase 2:** Layer-based tests for the broader app (models, views, forms across sales and payment)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Test runner | pytest + pytest-django | Industry standard, better output, fixtures via conftest, powerful selection |
| Database | Real PostgreSQL | App uses django-tenants which requires PostgreSQL; avoids false positives from engine differences |
| Coverage | pytest-cov | Track progress from zero, identify gaps, minimal setup cost |
| Test data | factory-boy | Complex models (Invoice has many fields/relations); factories provide one-line creation with overrides |
| HTTP mocking | responses | Mock NGSign API calls without hitting the sandbox; deterministic, fast |
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
addopts = --cov=gov --cov=sales --cov=payment --cov-report=term-missing --tb=short
```

### Directory Structure

```
tests/
  __init__.py
  conftest.py                    # shared fixtures: tenant, user, logged_in_client
  factories.py                   # all factory-boy factories
  gov/
    __init__.py
    test_async_submission.py     # async submit views + thread function
    test_notification_api.py     # ngsign_pending_api endpoint
    test_ngsign_service.py       # service layer (submit, check_status)
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
```

All DB-hitting tests use `@pytest.mark.django_db(transaction=True)` since django-tenants needs real transactions for schema switching.

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
    rate = factory.Faker('pydecimal', left_digits=3, right_digits=3, positive=True)

class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Invoice'

    client = factory.SubFactory(ClientFactory)
    uniqueId = factory.Sequence(lambda n: f'FA-{n:03d}-2026')
    date_created = factory.LazyFunction(timezone.now)
    status = 'CURRENT'
    tva = 19
    discount = 0

class CreditNoteFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.CreditNote'

    client = factory.SubFactory(ClientFactory)
    uniqueId = factory.Sequence(lambda n: f'AV-{n:03d}-2026')
    date_created = factory.LazyFunction(timezone.now)
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

    invoice = factory.SubFactory(InvoiceFactory)
    unsigned_xml = b'<TEIF>test</TEIF>'
    status = 'draft'
    ngsign_status = None

class NGSignClientAccountFactory(DjangoModelFactory):
    class Meta:
        model = 'tenants.NGSignClientAccount'

    org_uuid = factory.Faker('uuid4')
    org_jwt = factory.Faker('sha256')
    signer_email = factory.LazyAttribute(lambda o: f'signer@{o.tenant.name.lower().replace(" ", "")}.com')
    status = 'ACTIVE'
```

---

## 3. Phase 1: NGSign Feature Tests

### test_async_submission.py

Tests for `invoice_ngsign_submit`, `avoir_ngsign_submit`, and `_process_ngsign_submission`:

| Test | What it verifies |
|------|-----------------|
| `test_submit_creates_gov_invoice_with_submitting_status` | POST creates GovInvoice with `ngsign_status='SUBMITTING'`, returns 200 with success JSON |
| `test_submit_duplicate_returns_409` | POST while existing GovInvoice has `SUBMITTING` status returns 409 |
| `test_submit_after_error_resets_status` | POST when existing GovInvoice has `ERROR` status resets to `SUBMITTING`, clears notes |
| `test_submit_nonexistent_invoice_returns_404` | POST with invalid invoice ID returns 404 |
| `test_submit_spawns_thread` | Mock `threading.Thread` to verify it's called with correct args and `.start()` is called |
| `test_submit_sets_submitted_at` | Verify `submitted_at` is set to current time on submit |
| `test_thread_sets_error_on_exception` | Call `_process_ngsign_submission` directly with mocked service that raises; verify `ngsign_status='ERROR'` and `notes` populated |
| `test_thread_closes_connection` | Call `_process_ngsign_submission` with mock; verify `connection.close()` called in all cases |
| `test_thread_generates_xml_when_missing` | Call with GovInvoice that has empty `unsigned_xml`; verify builder is called |
| `test_avoir_submit_creates_gov_invoice` | Same as invoice submit but for credit note FK |
| `test_avoir_submit_duplicate_returns_409` | Same guard logic for avoirs |
| `test_requires_login` | Anonymous POST returns 302 redirect |
| `test_requires_post` | GET returns 405 |

**Mocking strategy:** The thread function is tested directly (not via actual threading) by calling `_process_ngsign_submission()` synchronously. The NGSign API calls (`submit_invoice`) are mocked using `unittest.mock.patch`. The submit views mock `threading.Thread` to verify spawning without actually running the thread.

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
| `test_stale_submitting_promoted_to_error` | GovInvoice with `SUBMITTING` and `submitted_at` >60s ago appears in `errors`, DB updated |
| `test_fresh_submitting_stays_in_progress` | GovInvoice with `SUBMITTING` and `submitted_at` <60s ago stays in `in_progress` |
| `test_response_fields_for_invoice` | Verify `doc_type`, `doc_number`, `client_name`, `pds_url`, `detail_url` correct for invoice |
| `test_response_fields_for_avoir` | Same for credit note |
| `test_pds_url_null_when_no_uuid` | `pds_url` is `null` when `ngsign_transaction_uuid` is None |
| `test_total_count_correct` | `total` equals sum of all groups |
| `test_requires_login` | Anonymous GET returns 302 |
| `test_rejects_post` | POST returns 405 |

**Time mocking:** Stale detection tests use `freezegun` to freeze `timezone.now()` so the 60-second threshold is deterministic.

### test_ngsign_service.py

Tests for `submit_invoice`, `check_status`, `_get_account`:

| Test | What it verifies |
|------|-----------------|
| `test_submit_calls_build_payload_and_create_transaction` | Mocks both, verifies called with correct args |
| `test_submit_stores_transaction_and_invoice_uuids` | After submit, GovInvoice has correct UUIDs |
| `test_submit_sets_status_created` | After submit, `ngsign_status` is `CREATED` |
| `test_submit_raises_not_configured_when_no_account` | No NGSignClientAccount → raises `NGSignNotConfiguredError` |
| `test_submit_raises_not_configured_when_no_signer_email` | Account exists but `signer_email` empty → raises |
| `test_submit_raises_not_configured_when_account_error` | Account has `status='ERROR'` → raises |
| `test_submit_sets_error_on_api_failure` | Mock API to raise; verify `ngsign_status='ERROR'` |
| `test_check_status_updates_ngsign_status` | Mock API response; verify status updated on model |
| `test_check_status_fetches_signed_xml_on_ttn_signed` | When status is `TTN_SIGNED`, verify `get_signed_xml` called and stored |
| `test_check_status_fetches_signed_xml_on_ttn_transfered` | Same for `TTN_TRANSFERED` |
| `test_get_account_switches_schema` | Verify public schema switch and restore |

**Mocking strategy:** All NGSign API calls (`client.create_transaction`, `client.check_invoice_status`, `client.get_signed_xml`) are mocked with `unittest.mock.patch`. The `_get_account` function is tested by creating tenant + NGSignClientAccount fixtures.

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
| `test_line_items_match_invoice_services` | Number of `Lin` elements matches services, amounts correct |
| `test_totals_correct` | HT, TVA, timbre fiscal, TTC amounts match model calculations |
| `test_discount_section_present_when_discount` | `InvoiceAlc` present with correct amount when `discount > 0` |
| `test_discount_section_absent_when_no_discount` | `InvoiceAlc` absent when `discount == 0` |
| `test_avoir_has_single_line_item` | Credit note XML has exactly one `Lin` |
| `test_avoir_totals_no_timbre` | Timbre fiscal is `0.000` for avoirs |
| `test_raises_valueerror_no_client` | Invoice without client raises `ValueError` |
| `test_raises_valueerror_no_unique_id` | Invoice without uniqueId raises `ValueError` |
| `test_raises_valueerror_no_mf` | Missing MF on seller or client raises `ValueError` |
| `test_sanitize_strips_forbidden_chars` | `_sanitize` removes `%`, `/`, `<`, `>`, `&`, `"`, `'` |
| `test_condense_to_single_line` | Whitespace between tags removed, content preserved |

**No mocking needed:** These tests create real model instances via factories and verify the generated XML by parsing it with `lxml.etree`.

---

## 4. Phase 2: Broad App Coverage

Lower priority, layer-based tests for the existing app:

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
| `tests/conftest.py` | **Create**: shared fixtures (tenant, user, client) |
| `tests/factories.py` | **Create**: factory-boy factory classes |
| `tests/gov/__init__.py` | **Create**: package init |
| `tests/gov/test_async_submission.py` | **Create**: async submit + thread tests |
| `tests/gov/test_notification_api.py` | **Create**: pending API endpoint tests |
| `tests/gov/test_ngsign_service.py` | **Create**: service layer tests |
| `tests/gov/test_teif_builder.py` | **Create**: TEIF XML builder tests |
| `tests/sales/__init__.py` | **Create**: package init |
| `tests/sales/test_models.py` | **Create**: model business logic tests |
| `tests/sales/test_views.py` | **Create**: CRUD view tests |
| `tests/sales/test_forms.py` | **Create**: form validation tests |
| `tests/payment/__init__.py` | **Create**: package init |
| `tests/payment/test_models.py` | **Create**: payment model tests |

No changes to existing production code. No new production dependencies.
