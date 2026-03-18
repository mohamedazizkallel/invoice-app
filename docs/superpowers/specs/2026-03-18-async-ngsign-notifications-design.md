# Async NGSign Submission & Notification Bell

**Date:** 2026-03-18
**Status:** Draft
**Branch:** feature/ngsign-integration

## Problem

The current NGSign submission flow is synchronous — the UI blocks while the backend generates XML/PDF and calls the NGSign API (2-5 seconds). After submission, the user is auto-redirected to the PDS signing page, losing their place in the app. There is no centralized view of pending documents across invoices and avoirs.

## Solution

Two features:

1. **Async submission** — fire-and-forget via background thread, return immediately
2. **Notification bell** — navbar icon showing all documents with actionable NGSign statuses, with inline actions (sign, view, check)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Async mechanism | `threading.Thread` | Low volume, early-stage app. No infra overhead (Redis/Celery). Upgrade path clear. |
| Notification dropdown layout | Grouped by status | Clear priority hierarchy: "A signer" > "Erreurs" > "En cours" |
| PDS link behavior | Opens in new tab | User keeps the app open, can continue working |
| Polling strategy | Smart polling (30s, only when active docs exist) | Saves server load when nothing is pending |
| Submission feedback | Toast + bell update | Immediate confirmation + ongoing tracking |

---

## 1. Data & Model Changes

### GovInvoice model

Add one new `ngsign_status` choice:

```python
('SUBMITTING', 'SUBMITTING')  # Set before thread starts, transitional state
```

Add two new fields:

```python
notes = models.TextField(blank=True, default='')  # Stores error details for notification display
submitted_at = models.DateTimeField(null=True, blank=True)  # Set when ngsign_status → SUBMITTING
```

**Stale detection:** If a document stays in `SUBMITTING` for >60 seconds (compared against `submitted_at`), the notification system treats it as potentially failed.

**PDS URL:** Not stored as a field. Reconstructed at query time from `ngsign_transaction_uuid` via `client.get_pds_url(uuid)` (simple string formatting).

### New API endpoint

```
GET /api/ngsign/pending/
```

Returns all `GovInvoice` records with non-terminal `ngsign_status`. Grouped:

- **to_sign** — `CREATED`, `CONFIGURED`
- **errors** — `ERROR`, `TTN_REJECTED`, `TTN_NOTTRANSFERED`
- **in_progress** — `SUBMITTING`, `SIGNED`

Note: `MIXED` is unlikely in this app (single-invoice transactions) but grouped under "in_progress" if it occurs. `TTN_TRANSFERED` is terminal (document accepted by TTN).

Response:

```json
{
  "to_sign": [
    {
      "id": 1,
      "doc_type": "invoice",
      "doc_number": "FA-012-2026",
      "client_name": "ABC Corp",
      "pds_url": "https://sandbox.ng-sign.com/pds/#/teif/invoice/{uuid}",
      "status": "CREATED"
    }
  ],
  "errors": [...],
  "in_progress": [...],
  "total": 5
}
```

Terminal statuses excluded from results: `TTN_SIGNED`, `TTN_TRANSFERED`, `CANCELLED`.

**Query optimization:** Use `select_related('invoice__client', 'credit_note__client')` to avoid N+1 queries.

**Field derivation:**
- `doc_type`: `"invoice"` if `invoice` FK is set, `"avoir"` if `credit_note` FK is set
- `doc_number`: from `invoice.uniqueId` or `credit_note.uniqueId`
- `client_name`: from `invoice.client.clientname` or `credit_note.client.clientname`
- `pds_url`: reconstructed from `ngsign_transaction_uuid` via `client.get_pds_url()`. Set to `null` if `ngsign_transaction_uuid` is null (e.g., SUBMITTING or ERROR before transaction was created)
- `detail_url`: link to invoice/avoir detail page for "Voir" button navigation

**Authentication:** Requires `@login_required` and `@require_GET`. Tenant scoping is automatic via django-tenants schema routing. No CSRF token needed for GET requests.

**URL name:** `ngsign-pending-api` (consistent with existing hyphenated convention).

---

## 2. Async Submission Flow

### Current flow (removed)

```
Click → AJAX wait → Generate XML + PDF → Call NGSign → Return PDS URL → Redirect
```

### New flow

```
Click → Create GovInvoice(ngsign_status=SUBMITTING) → Spawn thread → Return immediately
         └─ Thread: Generate XML + PDF → Call NGSign → Update GovInvoice
```

### View changes

`invoice_ngsign_submit` and `avoir_ngsign_submit`:

1. Guard: if `GovInvoice` exists with `ngsign_status='SUBMITTING'`, return error JSON
2. Create/update `GovInvoice` with `ngsign_status='SUBMITTING'`, `status='draft'`, `submitted_at=now()`
3. Capture `schema_name = connection.schema_name`
4. Spawn `threading.Thread(target=_process_ngsign_submission, args=(gov_invoice.id, schema_name), daemon=True)`
5. Return JSON: `{"success": true, "message": "Document soumis en arrière-plan"}`

### Thread function

`_process_ngsign_submission(gov_invoice_id, schema_name)`:

**Multi-tenancy:** The thread receives the tenant `schema_name` as an argument (captured in the view before spawning). At the start, the thread calls `connection.set_schema(schema_name)` to route all queries to the correct tenant schema.

1. Set tenant schema: `connection.set_schema(schema_name)`
2. Load `GovInvoice` fresh from DB
3. Determine if invoice or credit note
4. Generate unsigned TEIF XML if not already present
5. Build payload (PDF + XML via `serializer.build_payload()`)
6. Call `service.submit_invoice(gov_invoice)`
7. **On success:** `ngsign_status` updated to `CREATED` by existing service code
8. **On error:** Set `ngsign_status='ERROR'`, save error message (truncated to 500 chars) to `notes` field
9. **Finally:** Call `connection.close()` to prevent connection leaks

**Note on `_get_account()`:** The service layer's `_get_account()` temporarily switches to the public schema to query `NGSignClientAccount`, then restores the tenant schema. This is safe within the thread because it is synchronous — the schema is always restored before any tenant-scoped query runs.

### Guard against duplicate submission

If a `GovInvoice` already exists with `ngsign_status='SUBMITTING'`, the view rejects the request with `{"success": false, "message": "Soumission déjà en cours"}`. This prevents race conditions from double-clicks or multiple tabs.

**Re-submission after ERROR:** Allowed. The view updates the existing `GovInvoice` record — sets `ngsign_status='SUBMITTING'`, clears `notes`, updates `submitted_at`. The thread creates a new NGSign transaction, which overwrites the old `ngsign_transaction_uuid` and `ngsign_invoice_uuid`.

### Error handling

- API errors: caught, status set to `ERROR`, message saved to `notes`
- Unexpected exceptions: caught by broad except, same treatment
- Server crash mid-thread: document stuck in `SUBMITTING` — detected by notification system as stale after 60s (compared to `submitted_at`)
- Connection cleanup: `connection.close()` in a `finally` block ensures no leaked DB connections

---

## 3. Notification Bell UI

### Navbar placement

```
[Logo]  ───────────────────  [Bell (5)]  [Avatar Username]  [Logout]
```

Bell icon with badge counter showing total non-terminal document count. Positioned to the left of the user profile avatar.

### Dropdown structure

Grouped by status with colored headers:

- **"A signer" (orange)** — documents awaiting signature (CREATED, CONFIGURED)
- **"Erreurs" (red)** — failed documents (ERROR, TTN_REJECTED, TTN_NOTTRANSFERED)
- **"En cours" (green)** — in-progress documents (SUBMITTING, SIGNED)

Each item shows document number and a context-appropriate action button.

### Action buttons

| Status | Button | Action |
|--------|--------|--------|
| CREATED, CONFIGURED | "Signer" (blue) | `window.open(pds_url, '_blank')` |
| ERROR | "Voir" (gray) | Navigate to invoice/avoir detail page |
| TTN_REJECTED, TTN_NOTTRANSFERED | "Voir" (gray) | Navigate to detail page |
| SUBMITTING | Spinner icon | No action, visual indicator only |
| SIGNED | "Check" (gray) | Trigger status check API call |

### Empty state

No badge on bell. Dropdown shows: "Aucun document en cours."

---

## 4. Polling Logic

1. **On page load:** fetch `GET /api/ngsign/pending/` once
2. **If `total > 0`:** start interval polling every 30 seconds
3. **If `total === 0`:** stop polling, clear interval
4. **On new submission:** immediately call `fetchNotifications()` (don't wait for next poll cycle)
5. **On dropdown action** (check, sign): refetch after action completes
6. **Tab visibility:** pause polling when `document.hidden === true`, resume on visibility change

**Toast for async feedback:** Since the submission returns JSON (not a Django messages redirect), the toast is created programmatically via JS, reusing the existing toast markup/styling in `base.html`.

---

## 5. Files Modified

| File | Changes |
|------|---------|
| `gov/models.py` | Add `SUBMITTING` choice, add `notes` TextField, add `submitted_at` DateTimeField, migration |
| `sales/views.py` | Modify submit views (async), add `_process_ngsign_submission()`, add `ngsign_pending_api` view |
| `sales/urls.py` | Add `api/ngsign/pending/` URL |
| `templates/partials/base.html` | Add bell icon, dropdown markup, polling JS |
| `templates/sales/invoice_detail_service.html` | Remove PDS redirect, add toast + bell refresh on submit |
| `templates/sales/avoir_detail.html` | Same as above |

No new template files. No new JS files. No new dependencies.
