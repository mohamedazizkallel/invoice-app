# Invoice & Avoir Custom Date/Number — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users optionally override the date and numeric part of the `uniqueId` when creating or editing invoices (FV-) and avoirs (AV-); auto-generate both when omitted.

**Architecture:** Add `generate_unique_id` classmethod to `Invoice` and `CreditNote` that validates a user-supplied number (or computes next). Views read two new POST fields, call the helper, and pass `uniqueId` + `date_created` to `.create()` / set on edit. `CreditNote.date_created` is migrated off `auto_now_add` to allow overrides. Edit flow is gated for `Invoice` (not locked, not paid) and open for `CreditNote`.

**Tech Stack:** Django 4.x, pytest-django, Bootstrap modal forms, Python 3.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `invoice/sales/models.py` | `Invoice.generate_unique_id`, `CreditNote.generate_unique_id`, remove `auto_now_add` on `CreditNote.date_created` | Modify |
| `invoice/sales/migrations/0XXX_creditnote_date_created_manual.py` | Migration dropping `auto_now_add` | Create |
| `invoice/sales/views.py` | Parse date/number in `invoice_create`, `invoice_edit`, `avoir_create`, `avoir_edit`; call helper; apply on edit with lock-gate | Modify |
| `invoice/templates/sales/invoice_service.html` | Add date + number inputs to create modal (line ~259) | Modify |
| `invoice/templates/sales/invoice_detail_service.html` | Add date + number inputs to edit modal (line ~785), gated by `{% if not invoice.is_locked and invoice.status != 'PAID' %}` | Modify |
| `invoice/templates/sales/avoirs.html` | Add date + number inputs to create modal (line ~192) | Modify |
| `invoice/templates/sales/avoir_detail.html` | Add date + number inputs to edit modal (line ~577) | Modify |
| `tests/sales/test_models.py` | Unit tests for `generate_unique_id` helpers | Modify |
| `tests/sales/test_invoice_views.py` | Integration tests for create/edit with new fields | Modify |
| `tests/sales/test_credit_note_views.py` | Integration tests for create/edit with new fields | Modify |
| `tests/factories.py` | Update `CreditNoteFactory` comment after migration | Modify |

---

## Task 1: Model helper — `Invoice.generate_unique_id`

**Files:**
- Modify: `invoice/sales/models.py` (add method to `Invoice` class near existing `save()` at line ~549)
- Test: `tests/sales/test_models.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/sales/test_models.py` (create file if only has stub; append at end otherwise):

```python
import pytest
from sales.models import Invoice


@pytest.mark.django_db(transaction=True)
class TestInvoiceGenerateUniqueId:
    def test_auto_starts_at_one(self, tenant, seller):
        assert Invoice.generate_unique_id(2026) == 'FV-001-2026'

    def test_auto_increments_from_max(self, tenant, seller):
        from tests.factories import InvoiceFactory
        InvoiceFactory(uniqueId='FV-005-2026')
        InvoiceFactory(uniqueId='FV-003-2026')
        assert Invoice.generate_unique_id(2026) == 'FV-006-2026'

    def test_auto_is_per_year(self, tenant, seller):
        from tests.factories import InvoiceFactory
        InvoiceFactory(uniqueId='FV-010-2025')
        assert Invoice.generate_unique_id(2026) == 'FV-001-2026'

    def test_manual_number_formats(self, tenant, seller):
        assert Invoice.generate_unique_id(2026, manual_number=42) == 'FV-042-2026'

    def test_manual_number_collision_raises(self, tenant, seller):
        from tests.factories import InvoiceFactory
        InvoiceFactory(uniqueId='FV-007-2026')
        with pytest.raises(ValueError, match='FV-007-2026'):
            Invoice.generate_unique_id(2026, manual_number=7)

    def test_manual_number_out_of_range_raises(self, tenant, seller):
        with pytest.raises(ValueError):
            Invoice.generate_unique_id(2026, manual_number=0)
        with pytest.raises(ValueError):
            Invoice.generate_unique_id(2026, manual_number=1000)

    def test_manual_number_excludes_self(self, tenant, seller):
        from tests.factories import InvoiceFactory
        inv = InvoiceFactory(uniqueId='FV-009-2026')
        assert Invoice.generate_unique_id(2026, manual_number=9, exclude_pk=inv.pk) == 'FV-009-2026'
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_models.py::TestInvoiceGenerateUniqueId -v
```

Expected: all fail with `AttributeError: type object 'Invoice' has no attribute 'generate_unique_id'`.

- [ ] **Step 3: Implement helper**

In `invoice/sales/models.py`, add this method to the `Invoice` class (place directly above the existing `save` method, around line 549):

```python
    @classmethod
    def generate_unique_id(cls, year, manual_number=None, exclude_pk=None):
        """Return formatted uniqueId like 'FV-005-2026'.

        If manual_number is given, validate range [1, 999] and check that no
        other Invoice row uses that number for the given year. Excludes the
        row identified by exclude_pk when provided (for edit flow).

        If manual_number is None, return max(existing numeric suffix for year) + 1,
        starting at 1 when no rows exist for that year.
        """
        year_str = str(year)
        suffix = f'-{year_str}'

        if manual_number is not None:
            if not isinstance(manual_number, int) or manual_number < 1 or manual_number > 999:
                raise ValueError('Numéro invalide (1–999)')
            formatted = f'FV-{manual_number:03d}-{year_str}'
            qs = cls.objects.filter(uniqueId=formatted)
            if exclude_pk is not None:
                qs = qs.exclude(pk=exclude_pk)
            if qs.exists():
                raise ValueError(f'Numéro {formatted} déjà utilisé')
            return formatted

        existing = cls.objects.filter(
            uniqueId__startswith='FV-',
            uniqueId__endswith=suffix,
        )
        max_num = 0
        for inv in existing:
            try:
                n = int(inv.uniqueId.split('-')[1])
            except (ValueError, IndexError):
                continue
            if n > max_num:
                max_num = n
        return f'FV-{max_num + 1:03d}-{year_str}'
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_models.py::TestInvoiceGenerateUniqueId -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add invoice/sales/models.py tests/sales/test_models.py
git commit -m "feat(sales): add Invoice.generate_unique_id helper"
```

---

## Task 2: Migration — drop `auto_now_add` on `CreditNote.date_created`

**Files:**
- Modify: `invoice/sales/models.py` (line ~607 in `CreditNote`)
- Create: `invoice/sales/migrations/0XXX_creditnote_date_created_manual.py` (Django-generated)

- [ ] **Step 1: Change the field in the model**

In `invoice/sales/models.py`, inside class `CreditNote` (around line 607), replace:

```python
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
```

with:

```python
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)
```

- [ ] **Step 2: Update `CreditNote.save` to set timestamps when missing**

In the same file, inside `CreditNote.save` (around line 622), change the body to:

```python
    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
        if not self.uniqueId:
            year = now.year
            last = CreditNote.objects.filter(
                uniqueId__startswith='AV-',
                uniqueId__endswith=f'-{year}'
            ).order_by('-date_created').first()
            if last and last.uniqueId:
                try:
                    num = int(last.uniqueId.split('-')[1]) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                num = 1
            self.uniqueId = f'AV-{num:03d}-{year}'
        if not self.slug:
            self.slug = slugify(self.uniqueId)
        self.last_updated = now
        super().save(*args, **kwargs)
```

- [ ] **Step 3: Generate the migration**

```bash
cd /home/aziz/projects/invoice-app/invoice && python manage.py makemigrations sales --name creditnote_date_created_manual
```

Expected: Django creates a new file under `invoice/sales/migrations/` with `AlterField` operations for `date_created` and `last_updated`.

- [ ] **Step 4: Run the migration**

```bash
cd /home/aziz/projects/invoice-app/invoice && python manage.py migrate_schemas
```

Expected: migration applied without errors.

- [ ] **Step 5: Run existing tests to confirm no regression**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_credit_note_views.py -v
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add invoice/sales/models.py invoice/sales/migrations/
git commit -m "refactor(sales): allow manual date_created on CreditNote"
```

---

## Task 3: Model helper — `CreditNote.generate_unique_id`

**Files:**
- Modify: `invoice/sales/models.py` (add to `CreditNote` class)
- Test: `tests/sales/test_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/sales/test_models.py`:

```python
@pytest.mark.django_db(transaction=True)
class TestCreditNoteGenerateUniqueId:
    def test_auto_starts_at_one(self, tenant, seller):
        from sales.models import CreditNote
        assert CreditNote.generate_unique_id(2026) == 'AV-001-2026'

    def test_auto_increments_from_max(self, tenant, seller):
        from sales.models import CreditNote
        from tests.factories import CreditNoteFactory
        CreditNoteFactory(uniqueId='AV-005-2026')
        CreditNoteFactory(uniqueId='AV-003-2026')
        assert CreditNote.generate_unique_id(2026) == 'AV-006-2026'

    def test_manual_number_formats(self, tenant, seller):
        from sales.models import CreditNote
        assert CreditNote.generate_unique_id(2026, manual_number=42) == 'AV-042-2026'

    def test_manual_number_collision_raises(self, tenant, seller):
        from sales.models import CreditNote
        from tests.factories import CreditNoteFactory
        CreditNoteFactory(uniqueId='AV-007-2026')
        with pytest.raises(ValueError, match='AV-007-2026'):
            CreditNote.generate_unique_id(2026, manual_number=7)

    def test_manual_number_out_of_range_raises(self, tenant, seller):
        from sales.models import CreditNote
        with pytest.raises(ValueError):
            CreditNote.generate_unique_id(2026, manual_number=0)
        with pytest.raises(ValueError):
            CreditNote.generate_unique_id(2026, manual_number=1000)

    def test_manual_number_excludes_self(self, tenant, seller):
        from sales.models import CreditNote
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory(uniqueId='AV-009-2026')
        assert CreditNote.generate_unique_id(2026, manual_number=9, exclude_pk=cn.pk) == 'AV-009-2026'
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_models.py::TestCreditNoteGenerateUniqueId -v
```

Expected: fail with `AttributeError: type object 'CreditNote' has no attribute 'generate_unique_id'`.

- [ ] **Step 3: Implement helper**

In `invoice/sales/models.py`, add to the `CreditNote` class (directly above `save`):

```python
    @classmethod
    def generate_unique_id(cls, year, manual_number=None, exclude_pk=None):
        """Return formatted uniqueId like 'AV-005-2026'. See Invoice.generate_unique_id."""
        year_str = str(year)
        suffix = f'-{year_str}'

        if manual_number is not None:
            if not isinstance(manual_number, int) or manual_number < 1 or manual_number > 999:
                raise ValueError('Numéro invalide (1–999)')
            formatted = f'AV-{manual_number:03d}-{year_str}'
            qs = cls.objects.filter(uniqueId=formatted)
            if exclude_pk is not None:
                qs = qs.exclude(pk=exclude_pk)
            if qs.exists():
                raise ValueError(f'Numéro {formatted} déjà utilisé')
            return formatted

        existing = cls.objects.filter(
            uniqueId__startswith='AV-',
            uniqueId__endswith=suffix,
        )
        max_num = 0
        for cn in existing:
            try:
                n = int(cn.uniqueId.split('-')[1])
            except (ValueError, IndexError):
                continue
            if n > max_num:
                max_num = n
        return f'AV-{max_num + 1:03d}-{year_str}'
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_models.py::TestCreditNoteGenerateUniqueId -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add invoice/sales/models.py tests/sales/test_models.py
git commit -m "feat(sales): add CreditNote.generate_unique_id helper"
```

---

## Task 4: View wiring — `invoice_create`

**Files:**
- Modify: `invoice/sales/views.py` (function `invoice_create`, line ~1162)
- Test: `tests/sales/test_invoice_views.py`

- [ ] **Step 1: Write the failing tests**

Append to class `TestInvoiceViews` in `tests/sales/test_invoice_views.py`:

```python
    def test_invoice_create_with_manual_number(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        resp = logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_number': '42',
        })
        assert resp.status_code == 302
        inv = Invoice.objects.filter(client=c).first()
        assert inv is not None
        assert inv.uniqueId.startswith('FV-042-')

    def test_invoice_create_manual_number_conflict(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory, InvoiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        InvoiceFactory(client=c, uniqueId='FV-005-2026')
        before = Invoice.objects.count()
        resp = logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_number': '5',
        })
        assert resp.status_code == 302
        assert Invoice.objects.count() == before  # no new row

    def test_invoice_create_with_manual_date(self, tenant, seller, logged_in_client):
        from datetime import date
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_date': '2025-06-15',
        })
        inv = Invoice.objects.filter(client=c).first()
        assert inv.date_created.date() == date(2025, 6, 15)
        assert inv.uniqueId.endswith('-2025')  # year from picked date

    def test_invoice_create_default_date_is_today(self, tenant, seller, logged_in_client):
        from django.utils import timezone
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
        })
        inv = Invoice.objects.filter(client=c).first()
        assert inv.date_created.date() == timezone.localtime(timezone.now()).date()

    def test_invoice_create_sequence_after_manual_jump(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Invoice
        c = ClientFactory()
        s = ServiceFactory()
        # Create manual FV-010-2026
        logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_number': '10', 'invoice_date': '2026-03-01',
        })
        # Next auto-invoice
        logged_in_client.post(reverse('invoice_create'), {
            'client': c.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'tva': '19', 'timbre_fiscal': '1.000', 'discount': '0',
            'invoice_date': '2026-03-02',
        })
        ids = sorted(Invoice.objects.values_list('uniqueId', flat=True))
        assert 'FV-010-2026' in ids
        assert 'FV-011-2026' in ids
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_invoice_views.py -v -k "manual_number or manual_date or default_date or sequence_after_manual"
```

Expected: fail (current view ignores the new fields).

- [ ] **Step 3: Update `invoice_create`**

In `invoice/sales/views.py`, locate `invoice_create` (line ~1162). Inside the `try / with transaction.atomic():` block, **before** the existing `invoice = Invoice.objects.create(...)` call (around line 1216), insert:

```python
            # Parse optional custom date
            from datetime import datetime, time
            from django.utils import timezone as dj_tz
            custom_date_raw = request.POST.get('invoice_date', '').strip()
            custom_datetime = None
            if custom_date_raw:
                try:
                    parsed = datetime.strptime(custom_date_raw, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError('Date invalide')
                tz = dj_tz.get_current_timezone()
                custom_datetime = dj_tz.make_aware(datetime.combine(parsed, time.min), tz)

            # Parse optional custom number
            custom_number_raw = request.POST.get('invoice_number', '').strip()
            manual_number = None
            if custom_number_raw:
                try:
                    manual_number = int(custom_number_raw)
                except ValueError:
                    raise ValueError('Numéro invalide (1–999)')

            # Determine year from picked date, else today
            year = (custom_datetime.year if custom_datetime
                    else dj_tz.localtime(dj_tz.now()).year)
            unique_id = Invoice.generate_unique_id(year, manual_number=manual_number)
```

Then change the existing `Invoice.objects.create(...)` call to include the new kwargs:

```python
            invoice_kwargs = dict(
                title=title,
                client=client,
                status=status,
                notes=notes,
                tva=tva,
                timbre_fiscal=timbre_fiscal,
                discount=discount,
                uniqueId=unique_id,
            )
            if custom_datetime is not None:
                invoice_kwargs['date_created'] = custom_datetime
            invoice = Invoice.objects.create(**invoice_kwargs)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_invoice_views.py -v
```

Expected: all TestInvoiceViews tests pass (existing + 5 new).

- [ ] **Step 5: Commit**

```bash
git add invoice/sales/views.py tests/sales/test_invoice_views.py
git commit -m "feat(sales): accept invoice_date and invoice_number on invoice_create"
```

---

## Task 5: View wiring — `invoice_edit` with lock/paid gate

**Files:**
- Modify: `invoice/sales/views.py` (function `invoice_edit`, line ~1273)
- Test: `tests/sales/test_invoice_views.py`

- [ ] **Step 1: Write the failing tests**

Append to `TestInvoiceViews`:

```python
    def test_invoice_edit_updates_date_and_number(self, tenant, seller, logged_in_client):
        from datetime import date
        from tests.factories import InvoiceFactory, ServiceFactory
        s = ServiceFactory()
        inv = InvoiceFactory(uniqueId='FV-001-2026', status='CURRENT', is_locked=False)
        resp = logged_in_client.post(reverse('invoice_edit', args=[inv.id]), {
            'client': inv.client.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'status': 'CURRENT',
            'invoice_number': '77', 'invoice_date': '2026-02-10',
        })
        assert resp.status_code == 302
        inv.refresh_from_db()
        assert inv.uniqueId == 'FV-077-2026'
        assert inv.date_created.date() == date(2026, 2, 10)

    def test_invoice_edit_locked_ignores_date_number(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ServiceFactory
        s = ServiceFactory()
        inv = InvoiceFactory(uniqueId='FV-002-2026', status='CURRENT', is_locked=True)
        original_id = inv.uniqueId
        original_date = inv.date_created
        logged_in_client.post(reverse('invoice_edit', args=[inv.id]), {
            'client': inv.client.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'status': 'CURRENT',
            'invoice_number': '99', 'invoice_date': '2020-01-01',
        })
        inv.refresh_from_db()
        assert inv.uniqueId == original_id
        assert inv.date_created == original_date

    def test_invoice_edit_paid_ignores_date_number(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ServiceFactory
        s = ServiceFactory()
        inv = InvoiceFactory(uniqueId='FV-003-2026', status='PAID', is_locked=False)
        original_id = inv.uniqueId
        logged_in_client.post(reverse('invoice_edit', args=[inv.id]), {
            'client': inv.client.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'status': 'PAID',
            'invoice_number': '88',
        })
        inv.refresh_from_db()
        assert inv.uniqueId == original_id

    def test_invoice_edit_number_collision_rejected(self, tenant, seller, logged_in_client):
        from tests.factories import InvoiceFactory, ServiceFactory
        s = ServiceFactory()
        InvoiceFactory(uniqueId='FV-050-2026')
        inv = InvoiceFactory(uniqueId='FV-004-2026', status='CURRENT', is_locked=False)
        logged_in_client.post(reverse('invoice_edit', args=[inv.id]), {
            'client': inv.client.id, 'service_id[]': [s.id], 'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'], 'status': 'CURRENT',
            'invoice_number': '50',
        })
        inv.refresh_from_db()
        assert inv.uniqueId == 'FV-004-2026'  # unchanged
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_invoice_views.py -v -k "edit_updates_date_and_number or edit_locked_ignores or edit_paid_ignores or edit_number_collision"
```

Expected: all 4 fail.

- [ ] **Step 3: Update `invoice_edit`**

In `invoice/sales/views.py`, inside `invoice_edit` after the existing numeric fields block (around line 1301, directly before the `# Client` comment), insert:

```python
            # Custom date / number — only when not locked and not paid
            if not invoice.is_locked and (status or invoice.status) != 'PAID':
                from datetime import datetime, time
                from django.utils import timezone as dj_tz

                custom_date_raw = request.POST.get('invoice_date', '').strip()
                if custom_date_raw:
                    try:
                        parsed = datetime.strptime(custom_date_raw, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError('Date invalide')
                    tz = dj_tz.get_current_timezone()
                    invoice.date_created = dj_tz.make_aware(
                        datetime.combine(parsed, time.min), tz
                    )

                custom_number_raw = request.POST.get('invoice_number', '').strip()
                if custom_number_raw:
                    try:
                        manual_number = int(custom_number_raw)
                    except ValueError:
                        raise ValueError('Numéro invalide (1–999)')
                    year = invoice.date_created.year if invoice.date_created else dj_tz.now().year
                    invoice.uniqueId = Invoice.generate_unique_id(
                        year, manual_number=manual_number, exclude_pk=invoice.pk,
                    )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_invoice_views.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add invoice/sales/views.py tests/sales/test_invoice_views.py
git commit -m "feat(sales): allow date/number edit on unlocked unpaid invoices"
```

---

## Task 6: View wiring — `avoir_create`

**Files:**
- Modify: `invoice/sales/views.py` (function `avoir_create`, line ~1725)
- Test: `tests/sales/test_credit_note_views.py`

- [ ] **Step 1: Write the failing tests**

Append to the existing test class in `tests/sales/test_credit_note_views.py` (if unsure of class name, open the file and append inside it):

```python
    def test_avoir_create_with_manual_number(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import CreditNote
        c = ClientFactory()
        resp = logged_in_client.post(reverse('avoir_create'), {
            'client': c.id, 'description': 'Test', 'amount_ht': '100.000', 'tva': '19',
            'invoice_number': '42',
        })
        assert resp.status_code == 302
        cn = CreditNote.objects.filter(client=c).first()
        assert cn is not None
        assert cn.uniqueId.startswith('AV-042-')

    def test_avoir_create_manual_number_conflict(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, CreditNoteFactory
        from sales.models import CreditNote
        c = ClientFactory()
        CreditNoteFactory(client=c, uniqueId='AV-005-2026')
        before = CreditNote.objects.count()
        logged_in_client.post(reverse('avoir_create'), {
            'client': c.id, 'description': 'X', 'amount_ht': '10.000', 'tva': '19',
            'invoice_number': '5',
        })
        assert CreditNote.objects.count() == before

    def test_avoir_create_with_manual_date(self, tenant, seller, logged_in_client):
        from datetime import date
        from tests.factories import ClientFactory
        from sales.models import CreditNote
        c = ClientFactory()
        logged_in_client.post(reverse('avoir_create'), {
            'client': c.id, 'description': 'X', 'amount_ht': '10.000', 'tva': '19',
            'invoice_date': '2025-06-15',
        })
        cn = CreditNote.objects.filter(client=c).first()
        assert cn.date_created.date() == date(2025, 6, 15)
        assert cn.uniqueId.endswith('-2025')

    def test_avoir_create_default_date_is_today(self, tenant, seller, logged_in_client):
        from django.utils import timezone
        from tests.factories import ClientFactory
        from sales.models import CreditNote
        c = ClientFactory()
        logged_in_client.post(reverse('avoir_create'), {
            'client': c.id, 'description': 'X', 'amount_ht': '10.000', 'tva': '19',
        })
        cn = CreditNote.objects.filter(client=c).first()
        assert cn.date_created.date() == timezone.localtime(timezone.now()).date()
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_credit_note_views.py -v -k "manual_number or manual_date or default_date"
```

Expected: fail.

- [ ] **Step 3: Update `avoir_create`**

In `invoice/sales/views.py`, `avoir_create` function (line ~1725). Inside the `try / with transaction.atomic():` block, directly **before** the existing `credit_note = CreditNote.objects.create(...)` call (around line 1767), insert:

```python
            from datetime import datetime, time
            from django.utils import timezone as dj_tz

            custom_date_raw = request.POST.get('invoice_date', '').strip()
            custom_datetime = None
            if custom_date_raw:
                try:
                    parsed = datetime.strptime(custom_date_raw, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError('Date invalide')
                tz = dj_tz.get_current_timezone()
                custom_datetime = dj_tz.make_aware(datetime.combine(parsed, time.min), tz)

            custom_number_raw = request.POST.get('invoice_number', '').strip()
            manual_number = None
            if custom_number_raw:
                try:
                    manual_number = int(custom_number_raw)
                except ValueError:
                    raise ValueError('Numéro invalide (1–999)')

            year = (custom_datetime.year if custom_datetime
                    else dj_tz.localtime(dj_tz.now()).year)
            unique_id = CreditNote.generate_unique_id(year, manual_number=manual_number)
```

Then change the existing `CreditNote.objects.create(...)` call to:

```python
            cn_kwargs = dict(
                client=client,
                invoice=linked_invoice,
                description=description,
                amount_ht=amount_ht,
                tva=tva,
                uniqueId=unique_id,
            )
            if custom_datetime is not None:
                cn_kwargs['date_created'] = custom_datetime
            credit_note = CreditNote.objects.create(**cn_kwargs)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_credit_note_views.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add invoice/sales/views.py tests/sales/test_credit_note_views.py
git commit -m "feat(sales): accept invoice_date and invoice_number on avoir_create"
```

---

## Task 7: View wiring — `avoir_edit`

**Files:**
- Modify: `invoice/sales/views.py` (function `avoir_edit`, line ~1797)
- Test: `tests/sales/test_credit_note_views.py`

- [ ] **Step 1: Write the failing tests**

Append to the same class in `tests/sales/test_credit_note_views.py`:

```python
    def test_avoir_edit_updates_date_and_number(self, tenant, seller, logged_in_client):
        from datetime import date
        from tests.factories import CreditNoteFactory
        cn = CreditNoteFactory(uniqueId='AV-001-2026')
        logged_in_client.post(reverse('avoir_edit', args=[cn.id]), {
            'description': 'Updated', 'amount_ht': '20.000', 'tva': '19',
            'invoice_number': '77', 'invoice_date': '2026-02-10',
        })
        cn.refresh_from_db()
        assert cn.uniqueId == 'AV-077-2026'
        assert cn.date_created.date() == date(2026, 2, 10)

    def test_avoir_edit_number_collision_rejected(self, tenant, seller, logged_in_client):
        from tests.factories import CreditNoteFactory
        CreditNoteFactory(uniqueId='AV-050-2026')
        cn = CreditNoteFactory(uniqueId='AV-004-2026')
        logged_in_client.post(reverse('avoir_edit', args=[cn.id]), {
            'description': 'X', 'amount_ht': '10.000', 'tva': '19',
            'invoice_number': '50',
        })
        cn.refresh_from_db()
        assert cn.uniqueId == 'AV-004-2026'
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_credit_note_views.py -v -k "edit_updates_date_and_number or edit_number_collision"
```

Expected: fail.

- [ ] **Step 3: Update `avoir_edit`**

In `invoice/sales/views.py`, inside `avoir_edit`, directly **before** `credit_note.save()` (around line 1832), insert:

```python
            from datetime import datetime, time
            from django.utils import timezone as dj_tz

            custom_date_raw = request.POST.get('invoice_date', '').strip()
            if custom_date_raw:
                try:
                    parsed = datetime.strptime(custom_date_raw, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError('Date invalide')
                tz = dj_tz.get_current_timezone()
                credit_note.date_created = dj_tz.make_aware(
                    datetime.combine(parsed, time.min), tz
                )

            custom_number_raw = request.POST.get('invoice_number', '').strip()
            if custom_number_raw:
                try:
                    manual_number = int(custom_number_raw)
                except ValueError:
                    raise ValueError('Numéro invalide (1–999)')
                year = credit_note.date_created.year if credit_note.date_created else dj_tz.now().year
                credit_note.uniqueId = CreditNote.generate_unique_id(
                    year, manual_number=manual_number, exclude_pk=credit_note.pk,
                )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/test_credit_note_views.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add invoice/sales/views.py tests/sales/test_credit_note_views.py
git commit -m "feat(sales): allow date/number edit on avoir_edit"
```

---

## Task 8: Template — invoice create modal

**Files:**
- Modify: `invoice/templates/sales/invoice_service.html` (around line 314, inside `<div class="row g-2">`)

- [ ] **Step 1: Add inputs to create modal**

In `invoice/templates/sales/invoice_service.html`, find the "Réduction (%)" input block (around line 314-317). Directly **after** that `<div class="col-md-3">…</div>` block, insert:

```html
                <div class="col-md-3">
                  <label class="form-label fw-semibold mb-1">Date (optionnel)</label>
                  <input type="date" class="form-control form-control-sm" name="invoice_date" placeholder="Aujourd'hui si vide">
                </div>

                <div class="col-md-3">
                  <label class="form-label fw-semibold mb-1">Numéro (optionnel)</label>
                  <input type="number" min="1" max="999" class="form-control form-control-sm" name="invoice_number" placeholder="Auto si vide">
                </div>
```

- [ ] **Step 2: Smoke check — open dev server, render the create modal**

```bash
cd /home/aziz/projects/invoice-app/invoice && python manage.py runserver 8000
```

Then visit `/invoices/` (or the tenant subdomain equivalent), click "Créer une nouvelle facture", verify the two new inputs render. Stop the server.

- [ ] **Step 3: Commit**

```bash
git add invoice/templates/sales/invoice_service.html
git commit -m "feat(ui): date + number inputs on invoice create modal"
```

---

## Task 9: Template — invoice edit modal (gated)

**Files:**
- Modify: `invoice/templates/sales/invoice_detail_service.html` (around line 785, inside the edit form)

- [ ] **Step 1: Find the insertion point**

Open `invoice/templates/sales/invoice_detail_service.html` and locate the edit form at line ~785 (`<form action="{% url 'invoice_edit' invoice.id %}" …>`). Inside the form body, find a suitable `<div class="row">` near the tva/timbre/discount fields.

- [ ] **Step 2: Add inputs (gated)**

Inside the edit form, near the other numeric fields, insert:

```html
{% if not invoice.is_locked and invoice.status != 'PAID' %}
<div class="col-md-3">
  <label class="form-label fw-semibold mb-1">Date (optionnel)</label>
  <input type="date" class="form-control form-control-sm" name="invoice_date"
         value="{{ invoice.date_created|date:'Y-m-d' }}">
</div>
<div class="col-md-3">
  <label class="form-label fw-semibold mb-1">Numéro (optionnel)</label>
  <input type="number" min="1" max="999" class="form-control form-control-sm"
         name="invoice_number" placeholder="Auto si vide">
</div>
{% endif %}
```

- [ ] **Step 3: Smoke check**

Run the dev server, open an unlocked non-paid invoice's edit modal, confirm the two inputs render. Open a locked or paid invoice, confirm they do NOT render.

- [ ] **Step 4: Commit**

```bash
git add invoice/templates/sales/invoice_detail_service.html
git commit -m "feat(ui): date + number inputs on invoice edit modal (gated)"
```

---

## Task 10: Template — avoir create modal

**Files:**
- Modify: `invoice/templates/sales/avoirs.html` (form starting line ~192)

- [ ] **Step 1: Add inputs**

In `invoice/templates/sales/avoirs.html`, inside the create form (line ~192), near the existing `tva`/`amount_ht` fields, insert two new fields:

```html
<div class="col-md-6">
  <label class="form-label fw-semibold mb-1">Date (optionnel)</label>
  <input type="date" class="form-control form-control-sm" name="invoice_date" placeholder="Aujourd'hui si vide">
</div>
<div class="col-md-6">
  <label class="form-label fw-semibold mb-1">Numéro (optionnel)</label>
  <input type="number" min="1" max="999" class="form-control form-control-sm" name="invoice_number" placeholder="Auto si vide">
</div>
```

- [ ] **Step 2: Smoke check**

Run dev server, open "Créer un avoir" modal, confirm the two inputs render.

- [ ] **Step 3: Commit**

```bash
git add invoice/templates/sales/avoirs.html
git commit -m "feat(ui): date + number inputs on avoir create modal"
```

---

## Task 11: Template — avoir edit modal

**Files:**
- Modify: `invoice/templates/sales/avoir_detail.html` (form starting line ~577)

- [ ] **Step 1: Add inputs**

Inside the edit form, insert:

```html
<div class="col-md-6">
  <label class="form-label fw-semibold mb-1">Date (optionnel)</label>
  <input type="date" class="form-control form-control-sm" name="invoice_date"
         value="{{ avoir.date_created|date:'Y-m-d' }}">
</div>
<div class="col-md-6">
  <label class="form-label fw-semibold mb-1">Numéro (optionnel)</label>
  <input type="number" min="1" max="999" class="form-control form-control-sm"
         name="invoice_number" placeholder="Auto si vide">
</div>
```

Context variable is `avoir` (set by `avoir_detail` view at `views.py:1905`).

- [ ] **Step 2: Smoke check**

Run dev server, open avoir detail edit, confirm inputs render.

- [ ] **Step 3: Commit**

```bash
git add invoice/templates/sales/avoir_detail.html
git commit -m "feat(ui): date + number inputs on avoir edit modal"
```

---

## Task 12: Factory cleanup + final regression pass

**Files:**
- Modify: `tests/factories.py` (remove obsolete comment)

- [ ] **Step 1: Remove obsolete comment**

In `tests/factories.py`, inside `CreditNoteFactory`, delete the line:

```python
    # date_created uses auto_now_add=True — cannot be overridden
```

- [ ] **Step 2: Run full `sales` test suite**

```bash
cd /home/aziz/projects/invoice-app/invoice && pytest ../tests/sales/ -v
```

Expected: all tests pass (existing + new).

- [ ] **Step 3: Manual E2E smoke**

Run dev server and run through each flow once:
1. Create invoice with custom number + past date → id reflects both, year derived from date.
2. Create invoice with only number → id reflects number, today used as date.
3. Create invoice with neither → old behavior (auto id, today).
4. Try duplicate number → error message, stays on list.
5. Edit unlocked/unpaid invoice's number → id updates.
6. Try to edit a locked invoice's number → id unchanged.
7. Repeat flows 1-4 for avoir.

- [ ] **Step 4: Commit**

```bash
git add tests/factories.py
git commit -m "chore(tests): drop obsolete CreditNote factory comment"
```

---

## Summary of commits

1. `feat(sales): add Invoice.generate_unique_id helper`
2. `refactor(sales): allow manual date_created on CreditNote`
3. `feat(sales): add CreditNote.generate_unique_id helper`
4. `feat(sales): accept invoice_date and invoice_number on invoice_create`
5. `feat(sales): allow date/number edit on unlocked unpaid invoices`
6. `feat(sales): accept invoice_date and invoice_number on avoir_create`
7. `feat(sales): allow date/number edit on avoir_edit`
8. `feat(ui): date + number inputs on invoice create modal`
9. `feat(ui): date + number inputs on invoice edit modal (gated)`
10. `feat(ui): date + number inputs on avoir create modal`
11. `feat(ui): date + number inputs on avoir edit modal`
12. `chore(tests): drop obsolete CreditNote factory comment`
