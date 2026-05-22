# NGSign Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate NGSign e-signing (Seal) into the invoice app so invoices are automatically signed and the signed XML is stored for TTN transmission via the existing elfatoora SOAP flow.

**Architecture:** A new `gov/ngsign/` module handles all NGSign REST calls (client.py), invoice serialization (serializer.py), and orchestration (service.py). A new `NGSignClientAccount` model in the `tenants` app (public schema) stores each tenant's NGSign org UUID and JWT. Org creation/update is triggered automatically on `Settings.save()`.

**Tech Stack:** Django 6, django-tenants, `requests` (already in requirements.txt), lxml (already installed)

**Spec:** `docs/superpowers/specs/2026-03-13-ngsign-integration-design.md`

---

## File Map

### New files
| File | Responsibility |
|---|---|
| `invoice/gov/ngsign/__init__.py` | Package marker |
| `invoice/gov/ngsign/client.py` | Raw HTTP calls: `create_org`, `update_org`, `refresh_jwt`, `test_connectivity`, `submit_seal`, `get_signed_xml`, `check_ttn_status` |
| `invoice/gov/ngsign/serializer.py` | Maps `Invoice` + `Settings` + `Client` → `invoiceTIEF` JSON payload |
| `invoice/gov/ngsign/service.py` | Orchestrates: load account → connectivity → serialize → sign → store result |
| `invoice/gov/ngsign/exceptions.py` | Custom exceptions: `NGSignNotConfiguredError`, `NGSignAuthError`, `NGSignAPIError`, `NGSignSubmissionError` |
| `invoice/tests/test_ngsign_client.py` | Tests for `client.py` (mocked HTTP) |
| `invoice/tests/test_ngsign_serializer.py` | Tests for `serializer.py` |
| `invoice/tests/test_ngsign_service.py` | Tests for `service.py` (mocked client) |

### Modified files
| File | Change |
|---|---|
| `invoice/tenants/models.py` | Add `NGSignClientAccount` model |
| `invoice/tenants/admin.py` | Register `NGSignClientAccount` with Verify action |
| `invoice/gov/models.py` | Add 3 fields to `GovInvoice` |
| `invoice/gov/apps.py` | Add `NGSIGNE_API` env var check in `ready()` |
| `invoice/sales/models.py` | Add `transaction.on_commit()` hook to `Settings.save()` |
| `invoice/sales/views.py` | Add `invoice_ngsign_submit`, `invoice_ngsign_check` views |
| `invoice/sales/urls.py` | Register 2 new URL patterns |
| `invoice/templates/sales/invoice_detail_service.html` | Add Submit button, confirmation modal, status badge |

---

## Chunk 1: Foundation — Model, Migration, Admin

### Task 1: Add `NGSignClientAccount` to `tenants/models.py`

**Files:**
- Modify: `invoice/tenants/models.py`
- Test: `invoice/tests/test_ngsign_models.py`

- [ ] **Step 1: Write the failing test**

Create `invoice/tests/test_ngsign_models.py`:

```python
import pytest
from tenants.models import NGSignClientAccount, Tenant

@pytest.mark.django_db
def test_ngsign_client_account_fields():
    """NGSignClientAccount has all required fields with correct defaults."""
    tenant = Tenant.objects.create(schema_name='test', name='Test Co')
    account = NGSignClientAccount.objects.create(
        tenant=tenant,
        org_uuid='test-uuid-123',
        org_jwt='test-jwt-token',
    )
    assert account.status == 'PENDING'
    assert account.org_uuid == 'test-uuid-123'
    assert account.last_verified_at is None
    assert account.notes == ''
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd invoice && python manage.py test tests.test_ngsign_models -v 2
```
Expected: `AttributeError: type object 'tenants.models' has no attribute 'NGSignClientAccount'`

- [ ] **Step 3: Add model to `tenants/models.py`**

Append to the end of `invoice/tenants/models.py`:

```python
class NGSignClientAccount(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'PENDING'),
        ('ACTIVE', 'ACTIVE'),
        ('ERROR', 'ERROR'),
    ]

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name='ngsign_account'
    )
    org_uuid = models.CharField(max_length=100, blank=True)
    org_jwt = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"NGSign: {self.tenant.name} [{self.status}]"
```

- [ ] **Step 4: Create and run migration**

```bash
cd invoice && python manage.py makemigrations tenants --name add_ngsign_client_account
python manage.py migrate_schemas --shared
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd invoice && python manage.py test tests.test_ngsign_models -v 2
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add invoice/tenants/models.py invoice/tenants/migrations/ invoice/tests/test_ngsign_models.py
git commit -m "feat: add NGSignClientAccount model to tenants app"
```

---

### Task 2: Add NGSign fields to `GovInvoice`

**Files:**
- Modify: `invoice/gov/models.py`

- [ ] **Step 1: Add fields to `GovInvoice`**

In `invoice/gov/models.py`, add to `GovInvoice`:

```python
    ngsign_transaction_uuid = models.CharField(max_length=100, null=True, blank=True)
    ngsign_invoice_uuid = models.CharField(max_length=100, null=True, blank=True)
    ngsign_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('CREATED', 'CREATED'),
            ('SIGNED', 'SIGNED'),
            ('TTN_ACCEPTED', 'TTN_ACCEPTED'),
            ('TTN_REJECTED', 'TTN_REJECTED'),
            ('CANCELLED', 'CANCELLED'),
            ('ERROR', 'ERROR'),
        ]
    )
```

- [ ] **Step 2: Create and run migration**

```bash
cd invoice && python manage.py makemigrations gov --name add_ngsign_fields_to_govinvoice
python manage.py migrate_schemas
```

- [ ] **Step 3: Commit**

```bash
git add invoice/gov/models.py invoice/gov/migrations/
git commit -m "feat: add ngsign_transaction_uuid, ngsign_invoice_uuid, ngsign_status to GovInvoice"
```

---

### Task 3: Register `NGSignClientAccount` in admin

**Files:**
- Modify: `invoice/tenants/admin.py`

- [ ] **Step 1: Add admin class to `tenants/admin.py`**

Add to `invoice/tenants/admin.py`:

```python
from tenants.models import NGSignClientAccount

@admin.register(NGSignClientAccount)
class NGSignClientAccountAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'status', 'org_uuid', 'last_verified_at')
    readonly_fields = ('org_uuid', 'created_at', 'last_verified_at', 'status', 'notes')
    actions = ['verify_connectivity']

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Show org_jwt as write-only — never display existing value
        if 'org_jwt' in form.base_fields:
            form.base_fields['org_jwt'].widget.attrs['placeholder'] = '********'
            if obj and obj.pk:
                form.base_fields['org_jwt'].required = False
                form.base_fields['org_jwt'].help_text = 'Laisser vide pour conserver le token existant.'
        return form

    def save_model(self, request, obj, form, change):
        connection.set_schema_to_public()
        # If org_jwt field was left blank on update, keep existing value
        if change and not form.cleaned_data.get('org_jwt'):
            obj.org_jwt = NGSignClientAccount.objects.get(pk=obj.pk).org_jwt
        super().save_model(request, obj, form, change)

    @admin.action(description='Vérifier la connectivité NGSign')
    def verify_connectivity(self, request, queryset):
        from gov.ngsign.service import verify_account
        for account in queryset:
            try:
                verify_account(account)
                self.message_user(request, f"{account.tenant.name}: connectivité OK ✓")
            except Exception as e:
                self.message_user(request, f"{account.tenant.name}: ERREUR — {e}", level='error')
```

Also add `from django.db import connection` at the top of `tenants/admin.py` if not already imported.

- [ ] **Step 2: Verify admin loads without errors**

```bash
cd invoice && python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add invoice/tenants/admin.py
git commit -m "feat: register NGSignClientAccount in Django admin with Vérifier action"
```

---

## Chunk 2: NGSign HTTP Client

### Task 4: Create exceptions and package

**Files:**
- Create: `invoice/gov/ngsign/__init__.py`
- Create: `invoice/gov/ngsign/exceptions.py`

- [ ] **Step 1: Create package and exceptions**

```bash
mkdir -p invoice/gov/ngsign
touch invoice/gov/ngsign/__init__.py
```

Create `invoice/gov/ngsign/exceptions.py`:

```python
class NGSignError(Exception):
    """Base exception for all NGSign errors."""
    pass

class NGSignNotConfiguredError(NGSignError):
    """No active NGSignClientAccount found for this tenant."""
    pass

class NGSignAuthError(NGSignError):
    """JWT is invalid and could not be refreshed."""
    pass

class NGSignAPIError(NGSignError):
    """Unexpected error response from NGSign API."""
    pass

class NGSignSubmissionError(NGSignError):
    """Invoice submission to NGSign failed."""
    pass
```

- [ ] **Step 2: Commit**

```bash
git add invoice/gov/ngsign/
git commit -m "feat: add gov/ngsign package with custom exceptions"
```

---

### Task 5: Add env var check to `gov/apps.py`

**Files:**
- Modify: `invoice/gov/apps.py`

- [ ] **Step 1: Add `ready()` check**

Replace contents of `invoice/gov/apps.py`:

```python
import os
from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class GovConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gov'

    def ready(self):
        if not os.environ.get('NGSIGNE_API'):
            raise ImproperlyConfigured(
                "NGSIGNE_API environment variable is required for NGSign integration. "
                "Add it to your .env file."
            )
```

- [ ] **Step 2: Verify startup check works**

```bash
cd invoice && NGSIGNE_API='' python manage.py check 2>&1 | grep -i "ngsigne\|improperly"
```
Expected: output contains `NGSIGNE_API environment variable is required`

```bash
cd invoice && python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add invoice/gov/apps.py
git commit -m "feat: validate NGSIGNE_API env var on startup in GovConfig.ready()"
```

---

### Task 6: Write `client.py` — HTTP layer

**Files:**
- Create: `invoice/gov/ngsign/client.py`
- Test: `invoice/tests/test_ngsign_client.py`

- [ ] **Step 1: Write failing tests**

Create `invoice/tests/test_ngsign_client.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from gov.ngsign.client import (
    INVOICE_API_BASE,
    PARTNER_API_BASE,
    create_org,
    update_org,
    refresh_jwt,
    test_connectivity,
    submit_seal,
    get_signed_xml,
    check_ttn_status,
)
from gov.ngsign.exceptions import NGSignAuthError, NGSignAPIError

PARTNER_JWT = 'partner-token'
ORG_JWT = 'org-token'
ORG_UUID = 'org-uuid-123'


def _mock_response(status_code, json_data=None, content=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    mock.content = content or b''
    return mock


class TestCreateOrg:
    @patch('gov.ngsign.client.requests.post')
    def test_creates_org_and_returns_uuid_and_jwt(self, mock_post):
        mock_post.return_value = _mock_response(200, {
            'object': {'uuid': 'new-uuid', 'jwt': 'new-jwt', 'name': 'Test Co'},
            'message': 'ok'
        })
        result = create_org(PARTNER_JWT, 'Test Co', 'Rue de la Paix, Tunis', 'test@co.com')
        assert result['uuid'] == 'new-uuid'
        assert result['jwt'] == 'new-jwt'

    @patch('gov.ngsign.client.requests.post')
    def test_raises_api_error_on_failure(self, mock_post):
        mock_post.return_value = _mock_response(400, {'message': 'Bad request'})
        with pytest.raises(NGSignAPIError):
            create_org(PARTNER_JWT, 'Test Co', 'Addr', 'test@co.com')


class TestTestConnectivity:
    @patch('gov.ngsign.client.requests.get')
    def test_returns_true_on_200(self, mock_get):
        mock_get.return_value = _mock_response(200, {'object': ['CREATED', 'SIGNED']})
        assert test_connectivity(ORG_JWT, ORG_UUID, PARTNER_JWT) is True

    @patch('gov.ngsign.client.requests.post')
    @patch('gov.ngsign.client.requests.get')
    def test_auto_refreshes_on_401(self, mock_get, mock_post):
        # First GET → 401, refresh → 200, second GET → 200
        mock_get.side_effect = [
            _mock_response(401),
            _mock_response(200, {'object': []}),
        ]
        mock_post.return_value = _mock_response(200, {
            'object': {'jwt': 'refreshed-jwt', 'uuid': ORG_UUID, 'name': 'X'}
        })
        new_jwt = test_connectivity(ORG_JWT, ORG_UUID, PARTNER_JWT)
        assert new_jwt == 'refreshed-jwt'

    @patch('gov.ngsign.client.requests.post')
    @patch('gov.ngsign.client.requests.get')
    def test_raises_auth_error_when_refresh_also_fails(self, mock_get, mock_post):
        mock_get.return_value = _mock_response(401)
        mock_post.return_value = _mock_response(401)
        with pytest.raises(NGSignAuthError):
            test_connectivity(ORG_JWT, ORG_UUID, PARTNER_JWT)


class TestSubmitSeal:
    @patch('gov.ngsign.client.requests.post')
    def test_returns_transaction_on_success(self, mock_post):
        mock_post.return_value = _mock_response(200, {
            'object': {
                'uuid': 'txn-uuid',
                'status': 'SIGNED',
                'invoices': [{'uuid': 'inv-uuid', 'status': 'SIGNED', 'invoiceNumber': '001'}]
            }
        })
        result = submit_seal(ORG_JWT, [{'invoiceTIEF': {}}])
        assert result['uuid'] == 'txn-uuid'
        assert result['invoices'][0]['uuid'] == 'inv-uuid'

    @patch('gov.ngsign.client.requests.post')
    def test_raises_api_error_on_401(self, mock_post):
        mock_post.return_value = _mock_response(401)
        with pytest.raises(NGSignAPIError):
            submit_seal(ORG_JWT, [])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd invoice && python manage.py test tests.test_ngsign_client -v 2 2>&1 | head -20
```
Expected: `ImportError: cannot import name 'create_org' from 'gov.ngsign.client'`

- [ ] **Step 3: Implement `client.py`**

Create `invoice/gov/ngsign/client.py`:

```python
import os
import base64
import requests
from gov.ngsign.exceptions import NGSignAuthError, NGSignAPIError

INVOICE_API_BASE = 'https://sandbox.ng-sign.com/server'
PARTNER_API_BASE = 'https://sandbox.ng-sign.com'

TIMEOUT = 30  # seconds


def _partner_jwt():
    return os.environ['NGSIGNE_API']


def _auth_headers(jwt):
    return {'Authorization': f'Bearer {jwt}', 'Content-Type': 'application/json'}


def create_org(partner_jwt, name, address, email, first_name=None):
    """
    Create a new NGSign organization for a tenant.
    Returns dict with 'uuid' and 'jwt'.
    """
    payload = {
        'name': name,
        'street': address,
        'country': 'TN',
        'partnerUser': {
            'email': email,
            'firstName': first_name or name,
            'lastName': '',
            'phoneNumber': '',
        }
    }
    resp = requests.post(
        f'{PARTNER_API_BASE}/protected/user/partner/create',
        json=payload,
        headers=_auth_headers(partner_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'create_org failed: {resp.status_code} — {resp.text}')
    return resp.json()['object']  # {'uuid': ..., 'jwt': ..., 'name': ...}


def update_org(partner_jwt, org_jwt, name, address, email, first_name=None):
    """
    Update an existing NGSign organization.
    Returns dict with 'uuid' and 'jwt'.
    """
    payload = {
        'name': name,
        'street': address,
        'country': 'TN',
        'partnerUser': {
            'email': email,
            'firstName': first_name or name,
            'lastName': '',
            'phoneNumber': '',
        },
        'jwt': org_jwt,
    }
    resp = requests.post(
        f'{PARTNER_API_BASE}/protected/user/partner/update',
        json=payload,
        headers=_auth_headers(partner_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'update_org failed: {resp.status_code} — {resp.text}')
    return resp.json()['object']


def refresh_jwt(partner_jwt, org_uuid):
    """
    Regenerate the JWT for an organization.
    Returns the new JWT string.
    """
    resp = requests.post(
        f'{PARTNER_API_BASE}/protected/user/partner/refresh/{org_uuid}',
        headers=_auth_headers(partner_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAuthError(f'refresh_jwt failed: {resp.status_code} — {resp.text}')
    return resp.json()['object']['jwt']


def test_connectivity(org_jwt, org_uuid, partner_jwt):
    """
    Verify org JWT is valid. Auto-refreshes on 401.
    Returns True if valid, or the new JWT string if refreshed.
    Raises NGSignAuthError if refresh also fails.
    """
    resp = requests.get(
        f'{INVOICE_API_BASE}/protected/invoice/status',
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code == 200:
        return True
    if resp.status_code == 401:
        # Try to refresh
        try:
            new_jwt = refresh_jwt(partner_jwt, org_uuid)
        except NGSignAuthError:
            raise NGSignAuthError('JWT invalide et rafraîchissement échoué.')
        # Retry with new JWT
        retry = requests.get(
            f'{INVOICE_API_BASE}/protected/invoice/status',
            headers=_auth_headers(new_jwt),
            timeout=TIMEOUT,
        )
        if retry.status_code == 200:
            return new_jwt  # Caller should store this
        raise NGSignAuthError('JWT invalide après rafraîchissement.')
    raise NGSignAPIError(f'test_connectivity unexpected status: {resp.status_code}')


def submit_seal(org_jwt, invoices_payload):
    """
    Submit invoices for automatic Seal signing.
    invoices_payload: list of invoice dicts (each with invoiceTIEF, etc.)
    Returns the transaction object dict.
    """
    body = {
        'invoices': invoices_payload,
        'notifyOwner': False,
        'sendToSigner': False,
    }
    resp = requests.post(
        f'{INVOICE_API_BASE}/protected/invoice/v2/transaction/seal',
        json=body,
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'submit_seal failed: {resp.status_code} — {resp.text}')
    return resp.json()['object']  # {'uuid': ..., 'status': ..., 'invoices': [...]}


def get_signed_xml(org_jwt, invoice_uuid):
    """
    Download the signed XML for an invoice.
    Returns raw XML bytes.
    """
    resp = requests.get(
        f'{INVOICE_API_BASE}/protected/invoice/xml/{invoice_uuid}',
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'get_signed_xml failed: {resp.status_code}')
    b64_content = resp.json()['object']
    return base64.b64decode(b64_content)


def check_ttn_status(org_jwt, invoice_uuid):
    """
    Force TTN status sync for an invoice.
    Returns the invoice status dict.
    """
    resp = requests.post(
        f'{INVOICE_API_BASE}/protected/invoice/check/{invoice_uuid}',
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'check_ttn_status failed: {resp.status_code}')
    return resp.json()['object']  # {'uuid': ..., 'status': ..., 'invoiceNumber': ..., 'ttnReference': ...}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd invoice && python manage.py test tests.test_ngsign_client -v 2
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add invoice/gov/ngsign/client.py invoice/tests/test_ngsign_client.py
git commit -m "feat: implement NGSign HTTP client (create_org, submit_seal, test_connectivity, etc.)"
```

---

## Chunk 3: Serializer

### Task 7: Implement `serializer.py`

**Files:**
- Create: `invoice/gov/ngsign/serializer.py`
- Test: `invoice/tests/test_ngsign_serializer.py`

- [ ] **Step 1: Write failing tests**

Create `invoice/tests/test_ngsign_serializer.py`:

```python
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from gov.ngsign.serializer import build_payload


def _make_service(title='Dev', uid='SVC-1', billing_type='flat',
                   unit_price=100, hours=None, days=None, units=None,
                   fodec=False):
    svc = MagicMock()
    svc.service.title = title
    svc.service.uniqueId = uid
    svc.service.billing_type = billing_type
    svc.unit_price = Decimal(str(unit_price))
    svc.hours_used = hours
    svc.days_used = days
    svc.units_used = units
    svc.get_line_ht.return_value = Decimal(str(unit_price))
    svc.get_fodec_amount.return_value = Decimal('1.00') if fodec else Decimal('0')
    return svc


def _make_gov_invoice():
    gi = MagicMock()
    gi.unsigned_xml = b'<xml/>'

    invoice = MagicMock()
    invoice.title = 'INV-001'
    invoice.date_created.isoformat.return_value = '2026-03-13T10:00:00'
    invoice.get_tva.return_value = Decimal('19.00')
    invoice.calculate_service_subtotal.return_value = Decimal('850.000')
    invoice.calculate_tva_amount.return_value = Decimal('161.500')
    invoice.calculate_total.return_value = Decimal('1012.500')
    invoice.invoice_services.all.return_value = [_make_service()]
    invoice.client.mf = '1115438V'
    invoice.client.name = 'Client Co'
    invoice.client.adress = '10 Rue Example, Tunis'
    invoice.client.email = 'client@co.com'
    gi.invoice = invoice

    settings = MagicMock()
    settings.mf = '1953229C'
    settings.clientname = 'Swift Technology'
    settings.adress = 'Sfax, TN'

    gi._settings = settings
    return gi


@patch('gov.ngsign.serializer.Settings')
def test_build_payload_structure(mock_settings_class):
    gi = _make_gov_invoice()
    mock_settings_class.get_cached.return_value = gi._settings

    payload = build_payload(gi)

    assert payload['type'] == 'I_11'
    assert 'invoiceFileB64' in payload
    tief = payload['invoiceTIEF']
    assert tief['documentIdentifier'] == 'INV-001'
    assert tief['documentType'] == 'I-11'
    assert tief['supplierIdentifier'] == '1953229C'
    assert tief['clientIdentifier'] == '1115438V'
    assert len(tief['items']) == 1
    assert tief['invoiceTotalWithoutTax'] == pytest.approx(850.0)
    assert tief['invoiceTotalTax'] == pytest.approx(161.5)


@patch('gov.ngsign.serializer.Settings')
def test_flat_billing_maps_quantity_to_1(mock_settings_class):
    gi = _make_gov_invoice()
    mock_settings_class.get_cached.return_value = gi._settings
    payload = build_payload(gi)
    item = payload['invoiceTIEF']['items'][0]
    assert item['quantity'] == 1
    assert item['unit'] == 'C62'


@patch('gov.ngsign.serializer.Settings')
def test_hour_billing_maps_hours_used(mock_settings_class):
    gi = _make_gov_invoice()
    gi.invoice.invoice_services.all.return_value = [
        _make_service(billing_type='hour', hours=5)
    ]
    mock_settings_class.get_cached.return_value = gi._settings
    payload = build_payload(gi)
    item = payload['invoiceTIEF']['items'][0]
    assert item['quantity'] == 5
    assert item['unit'] == 'HUR'


@patch('gov.ngsign.serializer.Settings')
def test_fodec_included_as_tax_entry(mock_settings_class):
    gi = _make_gov_invoice()
    gi.invoice.invoice_services.all.return_value = [
        _make_service(fodec=True)
    ]
    mock_settings_class.get_cached.return_value = gi._settings
    payload = build_payload(gi)
    item_taxes = payload['invoiceTIEF']['items'][0]['taxes']
    tax_codes = [t['code'] for t in item_taxes]
    assert 'I-1602' in tax_codes   # TVA
    assert 'FODEC' in tax_codes
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd invoice && python manage.py test tests.test_ngsign_serializer -v 2 2>&1 | head -10
```
Expected: `ImportError: cannot import name 'build_payload'`

- [ ] **Step 3: Implement `serializer.py`**

Create `invoice/gov/ngsign/serializer.py`:

```python
import base64
from decimal import Decimal
from sales.models import Settings


UNIT_MAP = {
    'flat': ('C62', lambda svc: 1),
    'unit': ('C62', lambda svc: svc.units_used or 1),
    'hour': ('HUR', lambda svc: svc.hours_used or 1),
    'day':  ('DAY', lambda svc: svc.days_used or 1),
}


def _address(description):
    return {
        'description': description or '',
        'street': '',
        'cityName': '',
        'postalCode': '',
        'country': 'TN',
    }


def _item_taxes(invoice_service, tva_rate):
    """Build the taxes list for a single line item."""
    line_ht = invoice_service.get_line_ht()
    tva_amount = line_ht * (tva_rate / Decimal('100'))
    taxes = [
        {
            'code': 'I-1602',
            'taxRate': str(tva_rate),
            'amount': float(tva_amount.quantize(Decimal('0.001'))),
            'amountBase': float(line_ht.quantize(Decimal('0.001'))),
        }
    ]
    fodec = invoice_service.get_fodec_amount()
    if fodec > 0:
        taxes.append({
            'code': 'FODEC',
            'taxRate': '1.0',
            'amount': float(fodec.quantize(Decimal('0.001'))),
            'amountBase': float(line_ht.quantize(Decimal('0.001'))),
        })
    return taxes


def _build_item(invoice_service, tva_rate):
    billing_type = invoice_service.service.billing_type
    unit_code, qty_fn = UNIT_MAP.get(billing_type, UNIT_MAP['flat'])
    return {
        'name': invoice_service.service.title,
        'code': invoice_service.service.uniqueId,
        'unit': unit_code,
        'quantity': qty_fn(invoice_service),
        'tvaRate': float(tva_rate),
        'unitPrice': float(invoice_service.unit_price),
        'totalPrice': float(invoice_service.get_line_ht()),
        'taxes': _item_taxes(invoice_service, tva_rate),
    }


def build_payload(gov_invoice):
    """
    Build the NGSign invoice payload dict from a GovInvoice instance.
    Returns a single invoice dict suitable for inclusion in the 'invoices' list.
    """
    invoice = gov_invoice.invoice
    settings = Settings.get_cached()
    client = invoice.client
    tva_rate = invoice.get_tva()

    tief = {
        'documentIdentifier': invoice.title or invoice.uniqueId,
        'documentType': 'I-11',
        'invoiceDate': invoice.date_created.isoformat(),
        'currencyIdentifier': 'TND',

        'supplierIdentifier': settings.mf,
        'supplierDetails': {
            'partnerIdentifier': settings.mf,
            'partnerName': settings.clientname,
            'address': _address(settings.adress),
        },

        'clientIdentifier': client.mf,
        'clientDetails': {
            'partnerIdentifier': client.mf,
            'partnerName': client.name,
            'address': _address(client.adress),
        },

        'items': [
            _build_item(svc, tva_rate)
            for svc in invoice.invoice_services.all()
        ],

        'invoiceTotalWithoutTax': float(invoice.calculate_service_subtotal()),
        'invoiceTotalTax': float(invoice.calculate_tva_amount()),
        'invoiceTotalWithTax': float(invoice.calculate_total()),

        'taxes': [
            {
                'code': 'I-1602',
                'taxRate': str(tva_rate),
                'amount': float(invoice.calculate_tva_amount()),
                'amountBase': float(invoice.calculate_service_subtotal()),
            }
        ],
    }

    return {
        'type': 'I_11',
        'invoiceFileB64': base64.b64encode(bytes(gov_invoice.unsigned_xml)).decode(),
        'configuration': {
            'allPages': True,
            'qrPositionX': 0,
            'qrPositionY': 0,
            'qrPositionP': 0,
        },
        'invoiceTIEF': tief,
        'clientEmail': getattr(client, 'email', None) or '',
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd invoice && python manage.py test tests.test_ngsign_serializer -v 2
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add invoice/gov/ngsign/serializer.py invoice/tests/test_ngsign_serializer.py
git commit -m "feat: implement NGSign invoice serializer (Invoice → invoiceTIEF JSON)"
```

---

## Chunk 4: Service Layer + Settings Hook

### Task 8: Implement `service.py`

**Files:**
- Create: `invoice/gov/ngsign/service.py`
- Test: `invoice/tests/test_ngsign_service.py`

- [ ] **Step 1: Write failing tests**

Create `invoice/tests/test_ngsign_service.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from gov.ngsign.exceptions import NGSignNotConfiguredError, NGSignSubmissionError


def _mock_account(status='ACTIVE', org_jwt='org-jwt', org_uuid='org-uuid'):
    acc = MagicMock()
    acc.status = status
    acc.org_jwt = org_jwt
    acc.org_uuid = org_uuid
    return acc


class TestVerifyAccount:
    @patch('gov.ngsign.service.client.test_connectivity', return_value=True)
    def test_active_account_passes(self, mock_conn):
        from gov.ngsign.service import verify_account
        account = _mock_account()
        verify_account(account)
        mock_conn.assert_called_once()
        account.save.assert_called()

    @patch('gov.ngsign.service.client.test_connectivity', return_value='new-jwt')
    def test_refreshed_jwt_is_stored(self, mock_conn):
        from gov.ngsign.service import verify_account
        account = _mock_account()
        verify_account(account)
        assert account.org_jwt == 'new-jwt'


class TestSubmitInvoice:
    @patch('gov.ngsign.service.client.get_signed_xml', return_value=b'<signed/>')
    @patch('gov.ngsign.service.client.submit_seal')
    @patch('gov.ngsign.service.client.test_connectivity', return_value=True)
    @patch('gov.ngsign.service.serializer.build_payload', return_value={'type': 'I_11'})
    @patch('gov.ngsign.service._get_account')
    def test_successful_submission_stores_uuids(
        self, mock_get_acc, mock_serial, mock_conn, mock_seal, mock_xml
    ):
        from gov.ngsign.service import submit_invoice
        mock_get_acc.return_value = _mock_account()
        mock_seal.return_value = {
            'uuid': 'txn-uuid',
            'status': 'SIGNED',
            'invoices': [{'uuid': 'inv-uuid', 'status': 'SIGNED', 'invoiceNumber': '001'}]
        }
        gov_invoice = MagicMock()
        gov_invoice.invoice.client.mf = '123'

        submit_invoice(gov_invoice)

        assert gov_invoice.ngsign_transaction_uuid == 'txn-uuid'
        assert gov_invoice.ngsign_invoice_uuid == 'inv-uuid'
        assert gov_invoice.ngsign_status == 'SIGNED'
        assert gov_invoice.signed_xml == b'<signed/>'
        assert gov_invoice.status == 'signed'
        gov_invoice.save.assert_called()

    @patch('gov.ngsign.service._get_account')
    def test_missing_account_raises_not_configured(self, mock_get_acc):
        from gov.ngsign.service import submit_invoice
        mock_get_acc.return_value = None
        with pytest.raises(NGSignNotConfiguredError):
            submit_invoice(MagicMock())

    @patch('gov.ngsign.service._get_account')
    def test_error_status_account_raises_not_configured(self, mock_get_acc):
        from gov.ngsign.service import submit_invoice
        mock_get_acc.return_value = _mock_account(status='ERROR')
        with pytest.raises(NGSignNotConfiguredError):
            submit_invoice(MagicMock())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd invoice && python manage.py test tests.test_ngsign_service -v 2 2>&1 | head -10
```
Expected: `ImportError`

- [ ] **Step 3: Implement `service.py`**

Create `invoice/gov/ngsign/service.py`:

```python
import os
import logging
from django.utils import timezone
from django_tenants.utils import get_tenant

from gov.ngsign import client, serializer
from gov.ngsign.exceptions import (
    NGSignNotConfiguredError, NGSignAuthError, NGSignAPIError, NGSignSubmissionError
)

logger = logging.getLogger(__name__)


def _get_account():
    """Load NGSignClientAccount for the current tenant (public schema lookup)."""
    from django.db import connection
    from tenants.models import NGSignClientAccount
    try:
        schema = connection.schema_name
        connection.set_schema_to_public()
        # Get the Tenant for this schema
        from tenants.models import Tenant
        tenant = Tenant.objects.get(schema_name=schema)
        account = NGSignClientAccount.objects.filter(tenant=tenant).first()
        return account
    finally:
        connection.set_tenant(connection.tenant)


def verify_account(account):
    """
    Run connectivity check on an account, auto-refreshing JWT if needed.
    Updates account.status, account.last_verified_at, and account.org_jwt in-place.
    """
    partner_jwt = os.environ['NGSIGNE_API']
    result = client.test_connectivity(account.org_jwt, account.org_uuid, partner_jwt)
    if result is not True:
        # result is a new JWT string
        account.org_jwt = result
    account.status = 'ACTIVE'
    account.last_verified_at = timezone.now()
    account.save()


def submit_invoice(gov_invoice):
    """
    Sign a GovInvoice using NGSign Seal.
    On success: stores signed_xml, ngsign UUIDs, and sets status='signed'.
    On failure: raises NGSignSubmissionError.
    """
    account = _get_account()
    if not account or account.status == 'ERROR':
        raise NGSignNotConfiguredError(
            'NGSign non configuré pour ce tenant. '
            'Veuillez compléter vos paramètres.'
        )

    # Connectivity check + auto-refresh
    try:
        verify_account(account)
    except NGSignAuthError as e:
        raise NGSignNotConfiguredError(f'Authentification NGSign échouée: {e}')

    # Build payload
    payload = serializer.build_payload(gov_invoice)

    # Submit
    try:
        txn = client.submit_seal(account.org_jwt, [payload])
    except NGSignAPIError as e:
        gov_invoice.ngsign_status = 'ERROR'
        gov_invoice.save()
        raise NGSignSubmissionError(str(e))

    # Store transaction info
    gov_invoice.ngsign_transaction_uuid = txn['uuid']
    invoice_info = txn['invoices'][0]
    gov_invoice.ngsign_invoice_uuid = invoice_info['uuid']
    gov_invoice.ngsign_status = invoice_info['status']

    # Fetch signed XML
    try:
        signed_xml = client.get_signed_xml(account.org_jwt, invoice_info['uuid'])
        gov_invoice.signed_xml = signed_xml
        gov_invoice.status = 'signed'
    except NGSignAPIError as e:
        logger.warning(f'Signed XML fetch failed for {invoice_info["uuid"]}: {e}')
        # Transaction succeeded even if XML fetch fails — don't mark as error

    gov_invoice.save()
    return txn
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd invoice && python manage.py test tests.test_ngsign_service -v 2
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add invoice/gov/ngsign/service.py invoice/tests/test_ngsign_service.py
git commit -m "feat: implement NGSign service layer (submit_invoice, verify_account)"
```

---

### Task 9: Add `Settings.save()` org sync hook

**Files:**
- Modify: `invoice/sales/models.py`

- [ ] **Step 1: Add the hook to `Settings.save()`**

In `invoice/sales/models.py`, import at the top of the file (with other imports):

```python
from django.db import transaction as db_transaction
```

In `Settings.save()`, add at the end, after `super().save(*args, **kwargs)`:

```python
        db_transaction.on_commit(lambda: _sync_ngsign_org(self))
```

Then add this function **outside the class**, after the `Settings` class definition:

```python
def _sync_ngsign_org(settings_instance):
    """
    Called via on_commit after Settings.save().
    Creates or updates the NGSign org for the current tenant.
    All errors are caught and stored — this never raises.
    """
    import os
    import logging
    from django.db import connection
    from gov.ngsign import client
    from gov.ngsign.exceptions import NGSignAPIError

    logger = logging.getLogger(__name__)

    required = [
        settings_instance.clientname,
        settings_instance.emailAddress,
        settings_instance.adress,
        settings_instance.mf,
    ]
    if not all(required):
        return  # Not enough data yet

    partner_jwt = os.environ.get('NGSIGNE_API')
    if not partner_jwt:
        return

    current_schema = connection.schema_name
    try:
        connection.set_schema_to_public()
        from tenants.models import Tenant, NGSignClientAccount
        tenant = Tenant.objects.get(schema_name=current_schema)
        account, _ = NGSignClientAccount.objects.get_or_create(tenant=tenant)

        if not account.org_uuid:
            # First time — create org
            result = client.create_org(
                partner_jwt,
                settings_instance.clientname,
                settings_instance.adress,
                settings_instance.emailAddress,
            )
        else:
            # Update existing org
            result = client.update_org(
                partner_jwt,
                account.org_jwt,
                settings_instance.clientname,
                settings_instance.adress,
                settings_instance.emailAddress,
            )

        account.org_uuid = result['uuid']
        account.org_jwt = result['jwt']
        account.status = 'ACTIVE'
        account.notes = ''
        account.save()

    except Exception as e:
        logger.error(f'NGSign org sync failed for schema {current_schema}: {e}')
        try:
            account.status = 'ERROR'
            account.notes = str(e)
            account.save()
        except Exception:
            pass
    finally:
        connection.set_tenant_to_public()  # restore to public
        # Re-activate the tenant schema
        try:
            from tenants.models import Tenant
            t = Tenant.objects.get(schema_name=current_schema)
            connection.set_tenant(t)
        except Exception:
            pass
```

- [ ] **Step 2: Verify no import errors**

```bash
cd invoice && python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add invoice/sales/models.py
git commit -m "feat: auto-sync NGSign org on Settings.save() via on_commit hook"
```

---

## Chunk 5: Views, URLs, and UI

### Task 10: Add submit and check views

**Files:**
- Modify: `invoice/sales/views.py`
- Modify: `invoice/sales/urls.py`

- [ ] **Step 1: Add views to `sales/views.py`**

Add these two views at the end of `invoice/sales/views.py`:

```python
from django.http import JsonResponse
from django.views.decorators.http import require_POST

@login_required
@require_POST
def invoice_ngsign_submit(request, invoice_id):
    """Submit an invoice to NGSign for Seal signing."""
    from gov.models import GovInvoice
    from gov.ngsign.service import submit_invoice
    from gov.ngsign.exceptions import NGSignNotConfiguredError, NGSignSubmissionError

    invoice = get_object_or_404(Invoice, id=invoice_id)

    # Get or create GovInvoice (unsigned_xml must already exist)
    gov_invoice = GovInvoice.objects.filter(invoice=invoice).first()
    if not gov_invoice or not gov_invoice.unsigned_xml:
        return JsonResponse({
            'success': False,
            'error': 'XML non signable introuvable. Générez d\'abord le XML de la facture.'
        }, status=400)

    try:
        submit_invoice(gov_invoice)
        return JsonResponse({
            'success': True,
            'ngsign_status': gov_invoice.ngsign_status,
            'message': 'Facture soumise et signée avec succès.'
        })
    except NGSignNotConfiguredError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except NGSignSubmissionError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Erreur inattendue: {e}'}, status=500)


@login_required
@require_POST
def invoice_ngsign_check(request, invoice_id):
    """Force TTN status check for an invoice."""
    import os
    from gov.models import GovInvoice
    from gov.ngsign import client
    from gov.ngsign.exceptions import NGSignAPIError

    invoice = get_object_or_404(Invoice, id=invoice_id)
    gov_invoice = GovInvoice.objects.filter(invoice=invoice).first()

    if not gov_invoice or not gov_invoice.ngsign_invoice_uuid:
        return JsonResponse({
            'success': False,
            'error': 'Cette facture n\'a pas encore été soumise à NGSign.'
        }, status=400)

    try:
        from tenants.models import NGSignClientAccount
        from django.db import connection
        connection.set_schema_to_public()
        from tenants.models import Tenant
        tenant = Tenant.objects.get(schema_name=connection.schema_name)
        account = NGSignClientAccount.objects.filter(tenant=tenant).first()
        connection.set_tenant(tenant)

        result = client.check_ttn_status(account.org_jwt, gov_invoice.ngsign_invoice_uuid)
        gov_invoice.ngsign_status = result['status']
        gov_invoice.save()
        return JsonResponse({
            'success': True,
            'ngsign_status': gov_invoice.ngsign_status,
            'ttn_reference': result.get('ttnReference', ''),
        })
    except NGSignAPIError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
```

- [ ] **Step 2: Register URLs in `sales/urls.py`**

Add to `invoice/sales/urls.py` imports and urlpatterns:

```python
from sales.views import invoice_ngsign_submit, invoice_ngsign_check

# Add to urlpatterns:
path('invoices/<int:invoice_id>/ngsign/submit/', invoice_ngsign_submit, name='invoice-ngsign-submit'),
path('invoices/<int:invoice_id>/ngsign/check/', invoice_ngsign_check, name='invoice-ngsign-check'),
```

- [ ] **Step 3: Verify no errors**

```bash
cd invoice && python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add invoice/sales/views.py invoice/sales/urls.py
git commit -m "feat: add invoice_ngsign_submit and invoice_ngsign_check views"
```

---

### Task 11: Add UI — button, modal, status badge

**Files:**
- Modify: `invoice/templates/sales/invoice_detail_service.html`

- [ ] **Step 1: Add NGSign status badge**

Find the section in `invoice_detail_service.html` that displays invoice status badges and add after it:

```html
{% if gov_invoice.ngsign_status %}
<span class="badge {% if gov_invoice.ngsign_status == 'SIGNED' or gov_invoice.ngsign_status == 'TTN_ACCEPTED' %}bg-success{% elif gov_invoice.ngsign_status == 'ERROR' or gov_invoice.ngsign_status == 'TTN_REJECTED' %}bg-danger{% else %}bg-warning text-dark{% endif %}" id="ngsign-status-badge">
  NGSign: {{ gov_invoice.ngsign_status }}
</span>
{% endif %}
```

- [ ] **Step 2: Add "Soumettre à NGSign" button**

Find the invoice action buttons section and add:

```html
<button type="button"
        class="btn btn-primary"
        data-bs-toggle="modal"
        data-bs-target="#ngsignSubmitModal"
        data-invoice-id="{{ invoice.id }}"
        data-invoice-title="{{ invoice.title }}"
        data-client-name="{{ invoice.client.name }}"
        data-total="{{ invoice.calculate_total }}"
        data-date="{{ invoice.date_created|date:'d/m/Y' }}"
        data-current-status="{{ gov_invoice.ngsign_status|default:'' }}">
  Soumettre à NGSign
</button>

{% if gov_invoice.ngsign_invoice_uuid %}
<button type="button" class="btn btn-outline-secondary" id="btn-ngsign-check"
        data-invoice-id="{{ invoice.id }}">
  Vérifier statut TTN
</button>
{% endif %}
```

- [ ] **Step 3: Add confirmation modal**

Add before `{% endblock %}` in the template:

```html
<!-- NGSign Submit Confirmation Modal -->
<div class="modal fade" id="ngsignSubmitModal" tabindex="-1" aria-labelledby="ngsignSubmitModalLabel" aria-hidden="true">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="ngsignSubmitModalLabel">Soumettre à NGSign</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body" id="ngsign-modal-body">
        <!-- Filled by JS -->
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
        <button type="button" class="btn btn-primary" id="btn-ngsign-confirm">Soumettre</button>
      </div>
    </div>
  </div>
</div>

<script>
(function () {
  const modal = document.getElementById('ngsignSubmitModal');
  if (!modal) return;

  modal.addEventListener('show.bs.modal', function (event) {
    const btn = event.relatedTarget;
    const invoiceId = btn.dataset.invoiceId;
    const title = btn.dataset.invoiceTitle;
    const client = btn.dataset.clientName;
    const total = btn.dataset.total;
    const date = btn.dataset.date;
    const currentStatus = btn.dataset.currentStatus;

    const body = document.getElementById('ngsign-modal-body');
    const confirmBtn = document.getElementById('btn-ngsign-confirm');

    let html = '';
    if (currentStatus) {
      html += `<div class="alert alert-warning">Cette facture a déjà été soumise à NGSign (statut : <strong>${currentStatus}</strong>). Voulez-vous la soumettre à nouveau ?</div>`;
      confirmBtn.textContent = 'Soumettre quand même';
    } else {
      confirmBtn.textContent = 'Soumettre';
    }
    html += `<p><strong>Numéro :</strong> ${title}</p>`;
    html += `<p><strong>Client :</strong> ${client}</p>`;
    html += `<p><strong>Montant TTC :</strong> ${total} TND</p>`;
    html += `<p><strong>Date :</strong> ${date}</p>`;
    body.innerHTML = html;

    confirmBtn.onclick = function () {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Envoi en cours...';
      fetch(`/invoices/${invoiceId}/ngsign/submit/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '',
        },
      })
        .then(r => r.json())
        .then(data => {
          bootstrap.Modal.getInstance(modal).hide();
          if (data.success) {
            const badge = document.getElementById('ngsign-status-badge');
            if (badge) badge.textContent = 'NGSign: ' + data.ngsign_status;
            alert('✓ ' + data.message);
          } else {
            alert('Erreur : ' + data.error);
          }
          confirmBtn.disabled = false;
        })
        .catch(err => {
          alert('Erreur réseau : ' + err);
          confirmBtn.disabled = false;
        });
    };
  });

  // TTN status check button
  const checkBtn = document.getElementById('btn-ngsign-check');
  if (checkBtn) {
    checkBtn.addEventListener('click', function () {
      const invoiceId = checkBtn.dataset.invoiceId;
      checkBtn.disabled = true;
      fetch(`/invoices/${invoiceId}/ngsign/check/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '',
        },
      })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            const badge = document.getElementById('ngsign-status-badge');
            if (badge) badge.textContent = 'NGSign: ' + data.ngsign_status;
            alert(`Statut TTN : ${data.ngsign_status}${data.ttn_reference ? ' — Réf: ' + data.ttn_reference : ''}`);
          } else {
            alert('Erreur : ' + data.error);
          }
          checkBtn.disabled = false;
        });
    });
  }
})();
</script>
```

- [ ] **Step 4: Pass `gov_invoice` to template context**

In `invoice/sales/views.py`, in the `invoice_detail` view, add to the context:

```python
from gov.models import GovInvoice
gov_invoice = GovInvoice.objects.filter(invoice=invoice).first()
# Add to context dict:
'gov_invoice': gov_invoice,
```

- [ ] **Step 5: Run system check**

```bash
cd invoice && python manage.py check
```
Expected: no issues.

- [ ] **Step 6: Commit**

```bash
git add invoice/templates/sales/invoice_detail_service.html invoice/sales/views.py
git commit -m "feat: add NGSign submit button, confirmation modal, and status badge to invoice detail"
```

---

## Chunk 6: Manual Connectivity Test

### Task 12: Test the full flow manually in sandbox

- [ ] **Step 1: Run all tests**

```bash
cd invoice && python manage.py test tests.test_ngsign_client tests.test_ngsign_serializer tests.test_ngsign_service tests.test_ngsign_models -v 2
```
Expected: All PASS

- [ ] **Step 2: Test connectivity endpoint directly**

```python
# Run in Django shell: python manage.py shell
import os, requests
jwt = os.environ['NGSIGNE_API']
resp = requests.get(
    'https://sandbox.ng-sign.com/server/protected/invoice/status',
    headers={'Authorization': f'Bearer {jwt}'}
)
print(resp.status_code, resp.json())
```
Expected: `200` with a list of status strings — confirms the JWT is valid and the sandbox is reachable.

- [ ] **Step 3: Test Partner API connectivity**

```python
resp = requests.get(
    'https://sandbox.ng-sign.com/protected/invoice/status',
    headers={'Authorization': f'Bearer {jwt}'}
)
print(resp.status_code)
```
Use this to confirm the correct base URL for each API.

- [ ] **Step 4: Final commit — update spec with any findings**

If the base URLs or JWT scope differ from what was assumed, update `docs/ngsign/creation-invoice-api.md` and re-run any affected tests.

```bash
git add -A
git commit -m "docs: update NGSign integration notes after sandbox connectivity test"
```

---

## Notes for Phase 2 (Celery)

When ready to make submission asynchronous:

1. Install Celery + broker: `pip install celery redis`
2. Create `invoice/gov/ngsign/tasks.py`:
   ```python
   from celery import shared_task
   from gov.models import GovInvoice
   from gov.ngsign.service import submit_invoice

   @shared_task(bind=True, max_retries=3, default_retry_delay=60)
   def submit_invoice_task(self, gov_invoice_id):
       gov_invoice = GovInvoice.objects.get(id=gov_invoice_id)
       try:
           submit_invoice(gov_invoice)
       except Exception as exc:
           raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
   ```
3. In `invoice_ngsign_submit` view, replace:
   ```python
   submit_invoice(gov_invoice)
   ```
   with:
   ```python
   submit_invoice_task.delay(gov_invoice.id)
   ```
4. Return HTTP 202 instead of 200 from the view.
5. Add `org_jwt` encryption: `pip install django-fernet-fields`, replace `TextField` with `EncryptedTextField`.
