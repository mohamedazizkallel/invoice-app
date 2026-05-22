# Devis (Quote/Estimate) Feature Design

**Date:** 2026-03-06
**Status:** Approved

---

## Overview

Add a `Devis` (approximation invoice / quote) document type to the app. A devis is sent to a client before work begins. When the client accepts, a single button converts it into a real `Invoice` (`FV-###-YEAR`). The original devis is kept as a historical record linked to that invoice.

---

## Decisions

| Question | Decision |
|---|---|
| On acceptance | Creates a new Invoice, devis kept as historical record with FK to invoice |
| Locking | Never locked — always editable regardless of status |
| Statuses | `PENDING → ACCEPTED` or `PENDING → REJECTED` |

---

## Data Model

### `Devis` (added to `sales/models.py`)

| Field | Type | Notes |
|---|---|---|
| `client` | FK → Client | |
| `title` | CharField | |
| `notes` | TextField | |
| `status` | CharField | `PENDING`, `ACCEPTED`, `REJECTED` |
| `tva` | DecimalField | Same as Invoice — overrides Settings |
| `timbre_fiscal` | DecimalField | Same as Invoice |
| `discount` | DecimalField | Percentage |
| `converted_invoice` | OneToOneField → Invoice (null) | Populated on acceptance |
| `uniqueId` | CharField | `DV-001-2026`, sequential per year |
| `slug` | SlugField | unique |
| `date_created` | DateTimeField | |
| `last_updated` | DateTimeField | |

Key method: `convert_to_invoice()` — creates an `Invoice` + `InvoiceService` rows from the devis data, sets `converted_invoice`, sets `status = ACCEPTED`.

### `DevisService` (added to `sales/models.py`)

Mirrors `InvoiceService` exactly.

| Field | Type |
|---|---|
| `devis` | FK → Devis |
| `service` | FK → Service |
| `hours_used` | DecimalField |
| `days_used` | DecimalField |
| `units_used` | DecimalField |
| `unit_price` | DecimalField |
| `has_fodec` | BooleanField |

Same calculation methods as `InvoiceService`: `get_line_ht()`, `get_fodec_amount()`.

---

## Views & URLs

All views in `sales/views.py`, all `@login_required`.

| View | Method | URL | Action |
|---|---|---|---|
| `devis_list` | GET | `/devis/` | List all devis |
| `devis_create` | GET/POST | `/devis/create/` | Create devis + services |
| `devis_detail` | GET | `/devis/<slug>/` | View devis with totals |
| `devis_update` | GET/POST | `/devis/<slug>/update/` | Edit devis + services |
| `devis_delete` | GET/POST | `/devis/<slug>/delete/` | Delete confirmation |
| `devis_convert` | POST | `/devis/<slug>/convert/` | Convert to Invoice, redirect to invoice detail |

`devis_convert` guards: if `devis.converted_invoice` already exists, redirect immediately (idempotent).

---

## Templates

```
templates/
  devis/
    devis-list.html       — table with status badges (PENDING/ACCEPTED/REJECTED)
    devis-detail.html     — line items, totals, action buttons per status
    devis-create.html     — form + inline service rows
    devis-update.html     — same as create
    devis-delete.html     — confirmation
```

**Detail page buttons by status:**
- `PENDING` → "Convertir en Facture" (POST to convert), "Rejeter"
- `ACCEPTED` → link to `FV-###-YEAR` invoice, no convert button
- `REJECTED` → no action buttons, editable to reset to PENDING if needed

**PDF:** reuses existing invoice print template, header says `DEVIS` instead of `FACTURE`, shows `DV-###-YEAR`. No payment fields (no `amount_paid`, no retenues section).

---

## What does NOT change

- `Invoice` model — untouched
- `InvoiceService` model — untouched
- All existing views — untouched
- All existing templates — untouched
- Sequential invoice numbering (`FV-###-YEAR`) — untouched
