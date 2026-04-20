# Invoice & Avoir: Custom Date and Number — Design

**Date:** 2026-04-21
**Scope:** `sales` app — `Invoice` (FV-NNN-YYYY) and `CreditNote`/Avoir (AV-NNN-YYYY)

## Goal

Let users optionally override two fields when creating (and, with guards, editing) an invoice or avoir:

1. **Invoice date** — defaults to today if omitted.
2. **Invoice number** — the numeric part only (prefix `FV-` / `AV-` and year are fixed). Defaults to next sequential number if omitted.

## Requirements

- If date omitted → use today (`timezone.localtime(timezone.now())`).
- If number omitted → auto-increment per existing rule.
- User-supplied number uses **the same prefix and year** as auto-generation.
- If a user-supplied number collides with an existing id → **reject with an error message, no row created** (stay on form).
- After a manual number is saved, the auto-sequence continues from `max(existing) + 1` — manual jumps carry forward, never back-fill gaps.
- Year used for the sequence is **derived from the picked date's year**, not from "today". If no date picked, today's year.
- Edit flow allows changing date/number **only if** the invoice is not locked and not paid. Avoirs have no lock — allow always on edit.
- Date input is date-only (YYYY-MM-DD). Saved as local midnight in the existing `DateTimeField`.

## Non-goals

- No datetime-with-time picker.
- No "fill gap" sequencing mode.
- No changes to `Purchase`, `Devis`, `BonLivraison`.
- No admin panel changes.
- No migrations — existing fields already support both behaviors.

## Architecture

Approach **B** (from brainstorm): model-level helper classmethod, raw-POST views unchanged in shape.

### Model layer (`sales/models.py`)

Add classmethod to `Invoice` and `CreditNote`:

```python
@classmethod
def generate_unique_id(cls, year, manual_number=None):
    """
    Returns formatted uniqueId (e.g. 'FV-005-2026' / 'AV-012-2026').

    - manual_number given: validates 1..999, checks no collision for (prefix, year),
      returns formatted id. Raises ValueError on collision or out-of-range.
    - manual_number omitted: returns max(existing numeric suffix for year) + 1,
      formatted. Starts at 1 if no rows for that year.
    """
```

Prefix is hardcoded per class (`FV-` for Invoice, `AV-` for CreditNote), matching existing `save()` logic.

Keep existing `save()` auto-generation as fallback: if `self.uniqueId` is falsy it still derives one. The helper is called by views before `create()`; `save()` is not refactored.

### View layer (`sales/views.py`)

**`invoice_create` and `avoir_create`:**

1. Read `POST['invoice_date']` — if non-empty, parse `YYYY-MM-DD` → `datetime(Y, M, D, 0, 0, tzinfo=local)`. On parse failure: error message, redirect.
2. Read `POST['invoice_number']` — if non-empty, parse to `int`. Reject non-int or out-of-range with error message.
3. Determine `year`: picked date's year if date given, else `timezone.now().year`.
4. Call `Model.generate_unique_id(year, manual_number)` inside the existing `try/except` block. `ValueError` → `messages.error(...)` + redirect to list (matches existing error pattern).
5. Pass `uniqueId=<generated>` and, if date picked, `date_created=<parsed>` into the existing `Model.objects.create(...)` call.

**`invoice_edit` and `avoir_edit`:**

- Read the same two POST fields.
- Gate: for `Invoice`, skip applying either field if `invoice.is_locked or invoice.status == 'PAID'`. For `CreditNote`, allow always.
- If number changes: call `generate_unique_id(year, manual_number)` with collision check that **excludes self** (add `exclude_pk=self.pk` kwarg to the helper).
- If date changes: assign `invoice.date_created = parsed_date` before `.save()`.

### Template layer

**`templates/sales/invoices.html`** (create modal, edit modal):
**`templates/sales/avoirs.html`** (create modal, edit modal):

Add two inputs:

```html
<input type="date" name="invoice_date"
       placeholder="Aujourd'hui si vide">
<input type="number" name="invoice_number" min="1" max="999"
       placeholder="Auto si vide">
```

Edit modals wrap the two inputs in `{% if not invoice.is_locked and invoice.status != 'PAID' %}` (Invoice only; Avoir renders unconditionally).

## Data flow

```
POST (form)
  → view parses date + number
  → view computes year from date or now
  → Model.generate_unique_id(year, number) → id string OR ValueError
  → Model.objects.create(uniqueId=..., date_created=..., ...)
  → save() sees uniqueId set → skips auto-gen
  → ClientTransaction created as today (unchanged)
```

## Error handling

All errors raised as `messages.error(request, ...)` + redirect to list, matching existing patterns:

- Invalid date format → "Date invalide"
- Invalid number (non-int, <1, >999) → "Numéro invalide (1–999)"
- Collision → `f"Numéro {formatted_id} déjà utilisé"`

No partial state — wrapped in the existing `transaction.atomic()`.

## Testing (`sales/tests.py`)

Six tests per model (Invoice and CreditNote), 12 total:

1. `test_<model>_manual_number` — POST `invoice_number=42` → row has `FV-042-2026` / `AV-042-2026`.
2. `test_<model>_manual_number_conflict` — existing row, POST same number → error, row count unchanged.
3. `test_<model>_manual_date` — POST past date → `date_created` = that date, id uses that year.
4. `test_<model>_default_date_is_today` — no date POSTed → `date_created.date() == today`.
5. `test_<model>_sequence_after_manual_jump` — manual FV-010, then auto → FV-011.
6. `test_<model>_edit_locked_skips_date_number` (Invoice only; Avoir variant: confirm edit is always allowed).

## Files touched

| File | Change |
|---|---|
| `sales/models.py` | Add `Invoice.generate_unique_id`, `CreditNote.generate_unique_id` |
| `sales/views.py` | Extend `invoice_create`, `invoice_edit`, `avoir_create`, `avoir_edit` |
| `templates/sales/invoices.html` | Add date + number inputs to create and edit modals |
| `templates/sales/avoirs.html` | Add date + number inputs to create and edit modals |
| `sales/tests.py` | Add 12 tests |

## Build sequence

1. Add `generate_unique_id` helpers + unit tests for the helpers.
2. Wire into `invoice_create` + `avoir_create`; add create-flow integration tests.
3. Wire into `invoice_edit` + `avoir_edit` with lock/paid guard; add edit-flow tests.
4. Update templates.
5. Manual smoke: create, edit, collision, past-date, locked-edit.
