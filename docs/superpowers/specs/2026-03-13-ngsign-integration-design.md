# NGSign Integration Design

**Date:** 2026-03-13
**Branch:** to be created from `service_only`
**Status:** Approved

---

## Goal

Integrate NGSign e-signing API into the invoice app so that invoices are signed via electronic seal (SEAL) automatically. After receiving the signed XML from NGSign, the existing elfatoora SOAP flow transmits it to TTN.

---

## Context

- Stack: Django 6, django-tenants (schema-based multi-tenancy), lxml
- Existing: `gov/teif/` builds TEIF XML; `gov/teif/soap.py` submits signed XML to TTN via SOAP; `gov/models.py` has `GovInvoice` (stores unsigned/signed XML + status)
- New: `gov/ngsign/` handles signing step only (submit unsigned XML → receive signed XML)
- NGSign API base URLs:
  - Invoice API (signing): `https://sandbox.ng-sign.com/server`
  - Partner API (org management): `https://sandbox.ng-sign.com`
- Partner JWT stored in `NGSIGNE_API` env var
- API docs: `docs/ngsign/creation-invoice-api.md`, `docs/ngsign/partner-api.md`

---

## Revised Workflow

```
Invoice created
  → TEIF XML built (existing gov/teif/builder.py)
  → GovInvoice.unsigned_xml stored, status = "draft"
  → [NEW] Submit to NGSign via Seal endpoint (client's JWT)
  → NGSign returns signed XML
  → GovInvoice.signed_xml stored, status = "signed", ngsign_status = "SIGNED"
  → [EXISTING] Submit signed XML to TTN via elfatoora SOAP
  → GovInvoice.status = "sent"
  → TTN accept → status = "accepted"
  → TTN reject → status = "rejected"
```

NGSign is the **signing step only**. TTN transmission remains with the existing SOAP code.
`ngsign_status` tracks NGSign-specific state. `GovInvoice.status` tracks the overall document lifecycle. They are complementary, not overlapping.

---

## Architecture

### New module: `gov/ngsign/`

```
gov/ngsign/
  __init__.py
  client.py       # Raw HTTP calls to NGSign REST API
  serializer.py   # Maps Invoice + Settings → invoiceTIEF JSON + builds request payload
  service.py      # Orchestrates: load account → connectivity → serialize → sign → store result
```

### `NGSignClientAccount` model — in `tenants` app (already in SHARED_APPS / public schema)

```
tenants/
  models.py   ← add NGSignClientAccount here
  admin.py    ← register it here
```

---

## Data Model

### `NGSignClientAccount` (public schema, `tenants/models.py`)

| Field | Type | Notes |
|---|---|---|
| `tenant` | OneToOneField(Tenant) | Links to django-tenants Tenant model |
| `org_uuid` | CharField(100) | NGSign organization UUID |
| `org_jwt` | TextField | Client's signing JWT. Stored in plaintext for now — **must never be logged**. Encryption deferred to Phase 2. |
| `status` | CharField(20) | `PENDING` / `ACTIVE` / `ERROR` |
| `created_at` | DateTimeField(auto_now_add) | |
| `last_verified_at` | DateTimeField(null=True) | Updated on every successful connectivity check |
| `notes` | TextField(blank=True) | Error messages or ops notes |

### Updated `GovInvoice` fields (existing model, `gov/models.py`)

Add:

| Field | Type | Notes |
|---|---|---|
| `ngsign_transaction_uuid` | CharField(100, null=True) | NGSign transaction UUID |
| `ngsign_invoice_uuid` | CharField(100, null=True) | NGSign invoice UUID |
| `ngsign_status` | CharField(50, null=True) | `CREATED` / `SIGNED` / `TTN_ACCEPTED` / `TTN_REJECTED` / `CANCELLED` / `ERROR` |

`GovInvoice.status` lifecycle:
- `draft` → on creation
- `signed` → after NGSign seal succeeds
- `sent` → after SOAP submits to TTN
- `accepted` / `rejected` → after TTN response

---

## Automatic Org Creation (Settings → NGSign)

Hook into `Settings.save()` using `transaction.on_commit()` to safely defer the public schema write:

```python
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    transaction.on_commit(lambda: _create_ngsign_org_if_needed(self))
```

`_create_ngsign_org_if_needed(settings)`:
- Check required fields: `clientname`, `emailAddress`, `adress`, `mf`
- Check no `NGSignClientAccount` exists for current tenant
- Switch to public schema context
- Call `POST /protected/user/partner/create` (Partner API, `NGSIGNE_API` JWT)
  - Body: `name=clientname`, `street=adress`, `country="TN"`, `partnerUser.email=emailAddress`, `partnerUser.firstName=clientname`
  - Skip `fatooraDetails` for now (TTN linking deferred)
- Store `org_uuid` + `org_jwt`, status = `ACTIVE`
- On failure: create/update record with status = `ERROR`, store error in `notes`
- Restore tenant schema context after write
- **Does not raise — all errors are swallowed and stored in `notes`**

If account already exists: skip entirely.

---

## Connectivity Test & JWT Auto-Refresh

`client.test_connectivity(org_jwt, org_uuid)` → called by `service.py` before every submission and by the admin "Vérifier" action:

```
1. GET /protected/invoice/status  (Invoice API base, org_jwt)
   → 200: update last_verified_at, status = ACTIVE, return True
   → 401: call POST /protected/user/partner/refresh/{org_uuid}  (Partner API base, NGSIGNE_API JWT)
           → store new org_jwt in NGSignClientAccount
           → retry GET /protected/invoice/status with new jwt
             → 200: update last_verified_at, status = ACTIVE, return True
             → 401: set status = ERROR, notes = "JWT invalide après rafraîchissement", raise NGSignAuthError
   → other error: set status = ERROR, notes = error detail, raise NGSignAPIError
```

- Two distinct base URLs: Partner API calls use `https://sandbox.ng-sign.com`, Invoice API calls use `https://sandbox.ng-sign.com/server`
- `last_verified_at` updated on every successful 200 response
- Refresh is never called independently — always through `test_connectivity()`

---

## Invoice Submission Flow

`service.submit_invoice(gov_invoice)`:

```
1. Load NGSignClientAccount for current tenant
   → missing or status=ERROR: raise NGSignNotConfiguredError("NGSign non configuré pour ce tenant")

2. test_connectivity(account.org_jwt, account.org_uuid)
   → updates account.org_jwt in-place if refreshed

3. serializer.build_payload(gov_invoice) → dict with invoiceTIEF JSON + invoiceFileB64

4. POST /protected/invoice/v2/transaction/seal  (Invoice API, account.org_jwt)
   Full payload:
   {
     "invoices": [<serializer output>],
     "notifyOwner": false,
     "sendToSigner": false
   }

5. On success (200):
   → gov_invoice.ngsign_transaction_uuid = response["object"]["uuid"]
   → gov_invoice.ngsign_invoice_uuid = response["object"]["invoices"][0]["uuid"]
   → gov_invoice.ngsign_status = response["object"]["invoices"][0]["status"]
   → Fetch signed XML: GET /protected/invoice/xml/{ngsign_invoice_uuid}  (Invoice API, org_jwt)
   → gov_invoice.signed_xml = base64.decode(response["object"])
   → gov_invoice.status = "signed"
   → gov_invoice.save()
   → return True

6. On failure:
   → gov_invoice.ngsign_status = "ERROR"
   → gov_invoice.notes = error detail  (add notes field if not present)
   → gov_invoice.save()
   → raise NGSignSubmissionError(detail)
```

### Phase 2 (Celery) migration path

`service.py` exposes `submit_invoice(gov_invoice)` as a plain synchronous function.
To migrate to async, only the view changes:

```python
# Phase 1 (synchronous — blocks HTTP request for ~2-5s):
service.submit_invoice(gov_invoice)

# Phase 2 (Celery — returns immediately):
tasks.submit_invoice.delay(gov_invoice.id)
```

`client.py`, `serializer.py`, models, and templates require zero changes for this migration.

---

## Serializer (`serializer.py`)

`build_payload(gov_invoice)` reads from `gov_invoice.invoice` (the related `Invoice`) and its related `Settings`, `Client`, and `InvoiceService` records.

### Top-level payload fields

| Field | Value |
|---|---|
| `type` | `"I_11"` (underscore format — top-level field) |
| `invoiceFileB64` | `base64.b64encode(gov_invoice.unsigned_xml).decode()` |
| `configuration` | `{"allPages": true, "qrPositionX": 0, "qrPositionY": 0, "qrPositionP": 0}` |
| `clientEmail` | `invoice.client.email` if present, else omit |

### `invoiceTIEF` object

| NGSign field | Source |
|---|---|
| `documentType` | `"I-11"` (hyphen format — inside invoiceTIEF) |
| `documentIdentifier` | `invoice.title` (invoice number) |
| `invoiceDate` | `invoice.date_created.isoformat()` |
| `currencyIdentifier` | `"TND"` |
| `supplierIdentifier` | `settings.mf` |
| `supplierDetails.partnerIdentifier` | `settings.mf` |
| `supplierDetails.partnerName` | `settings.clientname` |
| `supplierDetails.address.description` | `settings.adress` (full string) |
| `supplierDetails.address.country` | `"TN"` |
| `clientIdentifier` | `invoice.client.mf` |
| `clientDetails.partnerIdentifier` | `invoice.client.mf` |
| `clientDetails.partnerName` | `invoice.client.name` |
| `clientDetails.address.description` | `invoice.client.adress` (full string) |
| `clientDetails.address.country` | `"TN"` |
| `invoiceTotalWithoutTax` | `float(invoice.calculate_service_subtotal())` (after discount) |
| `invoiceTotalTax` | `float(invoice.calculate_tva_amount())` |
| `invoiceTotalWithTax` | `float(invoice.calculate_total())` |
| `taxes` | List with one TVA entry (code `"I-1602"`, rate, amount) |

### `items` array (per `InvoiceService`)

| NGSign field | Source |
|---|---|
| `name` | `invoice_service.service.title` |
| `code` | `invoice_service.service.uniqueId` |
| `unit` | `"HUR"` if billing_type=hour, `"DAY"` if day, `"C62"` if unit or flat |
| `quantity` | `hours_used` / `days_used` / `units_used` / `1` (by billing_type) |
| `unitPrice` | `float(invoice_service.unit_price)` |
| `totalPrice` | `float(invoice_service.get_line_ht())` |
| `tvaRate` | `float(invoice.get_tva())` |
| `taxes` | TVA entry + FODEC entry if `get_fodec_amount() > 0` |

---

## UI Changes

### Invoice detail page (`templates/sales/invoice_detail.html` or equivalent)

- **"Soumettre à NGSign" button** — always visible
- Clicking opens a **confirmation modal** in French:
  - Normal state:
    ```
    Soumettre la facture à NGSign ?
    Numéro : [invoice.title]
    Client  : [client.name]
    Montant : [total TTC] TND
    Date    : [date_created]
    [Annuler]  [Soumettre]
    ```
  - Already submitted (`ngsign_status` not null):
    ```
    Cette facture a déjà été soumise à NGSign (statut : [ngsign_status]).
    Voulez-vous la soumettre à nouveau ?
    [Annuler]  [Soumettre quand même]
    ```
- On confirm: `POST /invoices/<id>/ngsign/submit/`
- After submission: `ngsign_status` badge displayed on invoice detail
- **"Vérifier statut TTN" button** — visible when `ngsign_invoice_uuid` is set; calls `POST /invoices/<id>/ngsign/check/`

### `invoice_ngsign_check` view

- Loads `GovInvoice` by `invoice_id`
- Calls `POST /protected/invoice/check/{ngsign_invoice_uuid}` (Invoice API, org_jwt)
- Updates `gov_invoice.ngsign_status` from response
- Returns JSON `{"status": "...", "message": "..."}` for AJAX update of badge

---

## Django Admin (`tenants/admin.py`)

`NGSignClientAccount` admin:
- List display: `tenant`, `status`, `last_verified_at`, `org_uuid`
- Read-only fields: `org_uuid`, `created_at`, `last_verified_at`, `status`, `notes`
- `org_jwt` displayed as `"********"` — shown as write-only (can set new value, never reads old)
- Action: **"Vérifier"** — runs `test_connectivity()`, updates `status` + `last_verified_at`, shows result message

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `NGSIGNE_API` env var missing | `ImproperlyConfigured` raised in `gov/apps.py` `AppConfig.ready()` |
| Settings save, org creation fails | Save succeeds; record created with `status=ERROR`; error in `notes`; error logged (not raised) |
| No `NGSignClientAccount` for tenant | Block submission; show "NGSign non configuré pour ce tenant" |
| `status=ERROR` on account | Block submission; show `notes` content as error message |
| 401 on submission | Auto-refresh JWT via `test_connectivity()`, retry once |
| Refresh also fails | `status=ERROR`; `NGSignAuthError` raised; shown as error message in view |
| NGSign API error | `ngsign_status=ERROR`; `NGSignSubmissionError` raised; `signed_xml` not updated |
| `org_jwt` | Never logged anywhere — treat as a secret |

---

## New URLs

```python
# In sales/urls.py (or gov/urls.py):
path('invoices/<int:invoice_id>/ngsign/submit/', views.invoice_ngsign_submit, name='invoice-ngsign-submit'),
path('invoices/<int:invoice_id>/ngsign/check/',  views.invoice_ngsign_check,  name='invoice-ngsign-check'),
```

Both views require `@login_required` and `@require_POST`.

---

## Files to Create/Modify

### New files
- `gov/ngsign/__init__.py`
- `gov/ngsign/client.py`
- `gov/ngsign/serializer.py`
- `gov/ngsign/service.py`
- `gov/migrations/XXXX_add_ngsign_fields_to_govinvoice.py`
- `tenants/migrations/XXXX_add_ngsign_client_account.py`

### Modified files
- `tenants/models.py` — add `NGSignClientAccount`
- `tenants/admin.py` — register `NGSignClientAccount`
- `gov/models.py` — add 3 fields to `GovInvoice`
- `gov/apps.py` — add `NGSIGNE_API` env var check in `ready()`
- `sales/models.py` — add `transaction.on_commit()` hook to `Settings.save()`
- `sales/views.py` — add `invoice_ngsign_submit`, `invoice_ngsign_check`
- `sales/urls.py` — register new URLs
- `templates/sales/invoice_detail.html` — button + modal + status badge
- `requirements.txt` — confirm `requests` is present

---

## Phase 2: Celery Migration (out of scope now)

When ready:
1. Add Celery + broker (Redis/RabbitMQ)
2. Create `gov/ngsign/tasks.py` with `@app.task def submit_invoice(gov_invoice_id)`
3. Replace synchronous view call with `.delay(gov_invoice_id)`
4. Add retry logic with exponential backoff inside the task
5. Add `org_jwt` encryption at rest (e.g. `django-fernet-fields`)
6. Add `ProviderRequestLog` model in `tenants` app for full audit trail (per `ngsign.md`)
