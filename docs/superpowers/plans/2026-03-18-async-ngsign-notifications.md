# Async NGSign Submission & Notification Bell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make NGSign submission async (fire-and-forget) and add a notification bell in the navbar showing all documents with actionable statuses.

**Architecture:** Background `threading.Thread` for async submission. New `GET /api/ngsign/pending/` endpoint returns grouped GovInvoice records. Bell icon in base.html header with dropdown, JS polling (30s) when active docs exist.

**Tech Stack:** Django, threading, Bootstrap Icons, vanilla JS (fetch API), existing Bootstrap 5 toast system.

**Spec:** `docs/superpowers/specs/2026-03-18-async-ngsign-notifications-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `invoice/gov/models.py` | Add `SUBMITTING` status, `notes` field, `submitted_at` field |
| `invoice/sales/views.py` | Async submit views, `_process_ngsign_submission()` thread fn, `ngsign_pending_api` view |
| `invoice/sales/urls.py` | Add `api/ngsign/pending/` URL |
| `invoice/templates/partials/base.html` | Bell icon + dropdown markup + notification JS + toast helper |
| `invoice/templates/sales/invoice_detail_service.html` | Remove PDS redirect, add toast + bell refresh |
| `invoice/templates/sales/avoir_detail.html` | Same as invoice template changes |

---

### Task 1: GovInvoice Model Changes

**Files:**
- Modify: `invoice/gov/models.py`

- [ ] **Step 1: Add SUBMITTING choice to ngsign_status**

In `invoice/gov/models.py`, add `('SUBMITTING', 'SUBMITTING')` as the first item in the `ngsign_status` choices list:

```python
ngsign_status = models.CharField(
    max_length=50,
    null=True,
    blank=True,
    choices=[
        ('SUBMITTING', 'SUBMITTING'),
        ('CREATED', 'CREATED'),
        ('CONFIGURED', 'CONFIGURED'),
        ('SIGNED', 'SIGNED'),
        ('CANCELLED', 'CANCELLED'),
        ('TTN_TRANSFERED', 'TTN_TRANSFERED'),
        ('TTN_NOTTRANSFERED', 'TTN_NOTTRANSFERED'),
        ('TTN_REJECTED', 'TTN_REJECTED'),
        ('TTN_SIGNED', 'TTN_SIGNED'),
        ('MIXED', 'MIXED'),
        ('ERROR', 'ERROR'),
    ]
)
```

- [ ] **Step 2: Add notes and submitted_at fields**

After the `ngsign_status` field, add:

```python
notes = models.TextField(blank=True, default='')
submitted_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 3: Generate and apply migration**

Run:
```bash
cd invoice && python manage.py makemigrations gov && python manage.py migrate
```

Expected: Migration `0005_*` created and applied successfully.

- [ ] **Step 4: Commit**

```bash
git add invoice/gov/models.py invoice/gov/migrations/0005_*
git commit -m "feat: add SUBMITTING status, notes and submitted_at fields to GovInvoice"
```

---

### Task 2: Thread Function & Async Submit Views

**Files:**
- Modify: `invoice/sales/views.py`

- [ ] **Step 1: Add _process_ngsign_submission thread function**

Add this function at the bottom of `invoice/sales/views.py` (after `avoir_ngsign_check`):

```python
def _process_ngsign_submission(gov_invoice_id, schema_name):
    """
    Background thread: generate XML/PDF, submit to NGSign, update GovInvoice.
    Runs outside the request cycle — must set tenant schema and close connection.
    """
    import logging
    from django.db import connection
    from django.utils import timezone

    logger = logging.getLogger(__name__)

    try:
        connection.set_schema(schema_name)
        from gov.models import GovInvoice
        from gov.ngsign.service import submit_invoice
        from gov.teif.builder import build_unsigned_teif, build_unsigned_teif_avoir
        from sales.models import Settings

        gov_invoice = GovInvoice.objects.get(id=gov_invoice_id)
        seller = Settings.get_cached()

        # Generate unsigned XML if missing
        if not gov_invoice.unsigned_xml:
            if gov_invoice.credit_note:
                gov_invoice.unsigned_xml = build_unsigned_teif_avoir(gov_invoice.credit_note, seller)
            else:
                gov_invoice.unsigned_xml = build_unsigned_teif(gov_invoice.invoice, seller)
            gov_invoice.save(update_fields=['unsigned_xml'])

        submit_invoice(gov_invoice)
        logger.info(f'NGSign submission succeeded for GovInvoice {gov_invoice_id}')

    except Exception as e:
        logger.exception(f'NGSign submission failed for GovInvoice {gov_invoice_id}')
        try:
            from gov.models import GovInvoice
            gov_invoice = GovInvoice.objects.get(id=gov_invoice_id)
            gov_invoice.ngsign_status = 'ERROR'
            gov_invoice.notes = str(e)[:500]
            gov_invoice.save(update_fields=['ngsign_status', 'notes'])
        except Exception:
            logger.exception(f'Failed to update error status for GovInvoice {gov_invoice_id}')
    finally:
        connection.close()
```

- [ ] **Step 2: Rewrite invoice_ngsign_submit to be async**

Replace the existing `invoice_ngsign_submit` function (lines 2592-2637, including decorators) with:

```python
@login_required
@require_POST
def invoice_ngsign_submit(request, invoice_id):
    """Submit an invoice to NGSign asynchronously."""
    import threading
    from django.db import connection
    from django.utils import timezone
    from gov.models import GovInvoice

    invoice = get_object_or_404(Invoice, id=invoice_id)

    gov_invoice = GovInvoice.objects.filter(invoice=invoice).first()

    # Guard: block if already submitting
    if gov_invoice and gov_invoice.ngsign_status == 'SUBMITTING':
        return JsonResponse({
            'success': False,
            'error': 'Soumission déjà en cours.'
        }, status=409)

    # Create or update GovInvoice
    if gov_invoice:
        gov_invoice.ngsign_status = 'SUBMITTING'
        gov_invoice.status = 'draft'
        gov_invoice.submitted_at = timezone.now()
        gov_invoice.notes = ''
        gov_invoice.save(update_fields=['ngsign_status', 'status', 'submitted_at', 'notes'])
    else:
        gov_invoice = GovInvoice.objects.create(
            invoice=invoice,
            unsigned_xml=b'',
            status='draft',
            ngsign_status='SUBMITTING',
            submitted_at=timezone.now(),
        )

    schema_name = connection.schema_name
    thread = threading.Thread(
        target=_process_ngsign_submission,
        args=(gov_invoice.id, schema_name),
        daemon=True,
    )
    thread.start()

    return JsonResponse({
        'success': True,
        'message': 'Document soumis en arrière-plan.'
    })
```

- [ ] **Step 3: Rewrite avoir_ngsign_submit to be async**

Replace the existing `avoir_ngsign_submit` function (lines 2668-2713, including decorators) with:

```python
@login_required
@require_POST
def avoir_ngsign_submit(request, avoir_id):
    """Submit a credit note (avoir) to NGSign asynchronously."""
    import threading
    from django.db import connection
    from django.utils import timezone
    from gov.models import GovInvoice
    from sales.models import CreditNote

    credit_note = get_object_or_404(CreditNote, id=avoir_id)

    gov_invoice = GovInvoice.objects.filter(credit_note=credit_note).first()

    # Guard: block if already submitting
    if gov_invoice and gov_invoice.ngsign_status == 'SUBMITTING':
        return JsonResponse({
            'success': False,
            'error': 'Soumission déjà en cours.'
        }, status=409)

    # Create or update GovInvoice
    if gov_invoice:
        gov_invoice.ngsign_status = 'SUBMITTING'
        gov_invoice.status = 'draft'
        gov_invoice.submitted_at = timezone.now()
        gov_invoice.notes = ''
        gov_invoice.save(update_fields=['ngsign_status', 'status', 'submitted_at', 'notes'])
    else:
        gov_invoice = GovInvoice.objects.create(
            credit_note=credit_note,
            unsigned_xml=b'',
            status='draft',
            ngsign_status='SUBMITTING',
            submitted_at=timezone.now(),
        )

    schema_name = connection.schema_name
    thread = threading.Thread(
        target=_process_ngsign_submission,
        args=(gov_invoice.id, schema_name),
        daemon=True,
    )
    thread.start()

    return JsonResponse({
        'success': True,
        'message': 'Document soumis en arrière-plan.'
    })
```

- [ ] **Step 4: Verify the app starts without errors**

Run:
```bash
cd invoice && python manage.py check
```

Expected: `System check identified no issues.`

- [ ] **Step 5: Commit**

```bash
git add invoice/sales/views.py
git commit -m "feat: make NGSign submission async via background thread"
```

---

### Task 3: Notification API Endpoint

**Files:**
- Modify: `invoice/sales/views.py`
- Modify: `invoice/sales/urls.py`

- [ ] **Step 1: Add ngsign_pending_api view**

Add to `invoice/sales/views.py` (after `_process_ngsign_submission`):

```python
@login_required
@require_GET
def ngsign_pending_api(request):
    """Return all GovInvoice records with non-terminal ngsign_status, grouped by category."""
    from django.urls import reverse
    from django.utils import timezone
    from gov.models import GovInvoice
    from gov.ngsign.client import get_pds_url

    TO_SIGN = {'CREATED', 'CONFIGURED'}
    ERRORS = {'ERROR', 'TTN_REJECTED', 'TTN_NOTTRANSFERED'}
    STALE_SECONDS = 60

    gov_invoices = (
        GovInvoice.objects
        .exclude(ngsign_status__in=['TTN_SIGNED', 'TTN_TRANSFERED', 'CANCELLED'])
        .exclude(ngsign_status__isnull=True)
        .exclude(ngsign_status='')
        .select_related('invoice__client', 'credit_note__client')
    )

    now = timezone.now()
    to_sign = []
    errors = []
    in_progress = []

    for gi in gov_invoices:
        if gi.invoice:
            doc_type = 'invoice'
            doc_number = gi.invoice.uniqueId
            client_name = gi.invoice.client.clientname if gi.invoice.client else ''
            detail_url = reverse('invoice_detail', args=[gi.invoice.id])
        elif gi.credit_note:
            doc_type = 'avoir'
            doc_number = gi.credit_note.uniqueId
            client_name = gi.credit_note.client.clientname if gi.credit_note.client else ''
            detail_url = reverse('avoir_detail', args=[gi.credit_note.id])
        else:
            continue

        # Stale detection: SUBMITTING for >60s is treated as ERROR
        status = gi.ngsign_status
        if status == 'SUBMITTING' and gi.submitted_at and (now - gi.submitted_at).total_seconds() > STALE_SECONDS:
            status = 'ERROR'
            gi.ngsign_status = 'ERROR'
            gi.notes = 'Soumission expirée (délai dépassé).'
            gi.save(update_fields=['ngsign_status', 'notes'])

        item = {
            'id': gi.id,
            'doc_type': doc_type,
            'doc_number': doc_number,
            'client_name': client_name,
            'status': status,
            'detail_url': detail_url,
            'pds_url': get_pds_url(gi.ngsign_transaction_uuid) if gi.ngsign_transaction_uuid else None,
            'notes': gi.notes or '',
        }

        if status in TO_SIGN:
            to_sign.append(item)
        elif status in ERRORS:
            errors.append(item)
        else:
            in_progress.append(item)

    return JsonResponse({
        'to_sign': to_sign,
        'errors': errors,
        'in_progress': in_progress,
        'total': len(to_sign) + len(errors) + len(in_progress),
    })
```

- [ ] **Step 2: Add require_GET import if not present**

Check the imports at top of `views.py`. The file currently imports `require_POST` from `django.views.decorators.http`. Add `require_GET` to that import:

```python
from django.views.decorators.http import require_POST, require_GET
```

- [ ] **Step 3: Add URL pattern and import**

In `invoice/sales/urls.py`, add `ngsign_pending_api` to the import list at line 22-23:

```python
                    invoice_ngsign_submit, invoice_ngsign_check,
                    avoir_ngsign_submit, avoir_ngsign_check,
                    ngsign_pending_api)
```

Add the URL pattern after the avoir ngsign URLs (after line 92):

```python
    # NGSign API
    path('api/ngsign/pending/', ngsign_pending_api, name='ngsign-pending-api'),
```

- [ ] **Step 4: Verify the app starts**

Run:
```bash
cd invoice && python manage.py check
```

Expected: `System check identified no issues.`

- [ ] **Step 5: Commit**

```bash
git add invoice/sales/views.py invoice/sales/urls.py
git commit -m "feat: add ngsign_pending_api endpoint for notification bell"
```

---

### Task 4: Notification Bell — Markup & CSS in base.html

**Files:**
- Modify: `invoice/templates/partials/base.html`

- [ ] **Step 1: Add notification bell CSS**

In `invoice/templates/partials/base.html`, add the following CSS inside the `<style>` block (after the `.user-avatar` styles, around line 104):

```css
/* Notification Bell */
.notification-wrapper {
  position: relative;
}

.notification-bell {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.85);
  font-size: 1.25rem;
  padding: 0.4rem 0.6rem;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
}

.notification-bell:hover {
  color: white;
  transform: translateY(-1px);
}

.notification-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  background: #e74c3c;
  color: white;
  font-size: 0.65rem;
  font-weight: 700;
  min-width: 16px;
  height: 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  line-height: 1;
}

.notification-dropdown {
  display: none;
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 340px;
  max-height: 420px;
  overflow-y: auto;
  background: #1a1d29;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.3);
  z-index: 2100;
  padding: 0;
}

.notification-dropdown.show { display: block; }

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.notification-header-title {
  color: white;
  font-weight: 600;
  font-size: 0.85rem;
}

.notification-group-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 10px 14px 4px;
}

.notification-group-label.to-sign { color: #f39c12; }
.notification-group-label.errors { color: #e74c3c; }
.notification-group-label.in-progress { color: #2ecc71; }

.notification-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  margin: 0 8px 4px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
}

.notification-item-info {
  display: flex;
  flex-direction: column;
}

.notification-item-number {
  color: white;
  font-weight: 500;
  font-size: 0.8rem;
}

.notification-item-client {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.7rem;
}

.notification-item-action {
  border: none;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 0.7rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.notification-item-action.sign { background: #3498db; color: white; }
.notification-item-action.view { background: rgba(255,255,255,0.15); color: white; }
.notification-item-action.check { background: rgba(255,255,255,0.15); color: white; }

.notification-empty {
  padding: 24px;
  text-align: center;
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.8rem;
}

.notification-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.2);
  border-top-color: #3498db;
  border-radius: 50%;
  animation: notif-spin 0.8s linear infinite;
}

@keyframes notif-spin {
  to { transform: rotate(360deg); }
}
```

- [ ] **Step 2: Add bell icon markup in header**

In `invoice/templates/partials/base.html`, find the header section (around line 519). Insert the notification bell **before** the `user-profile` div:

Replace this block (lines 519-533):
```html
    <div class="d-flex align-items-center gap-2">
      <button class="navbar-toggler d-md-none text-white border-0 p-2" type="button" onclick="toggleSidebar()">
        <i class="bi bi-list fs-4"></i>
      </button>
      <div class="user-profile d-none d-md-flex">
```

With:
```html
    <div class="d-flex align-items-center gap-2">
      <button class="navbar-toggler d-md-none text-white border-0 p-2" type="button" onclick="toggleSidebar()">
        <i class="bi bi-list fs-4"></i>
      </button>
      {% if user.is_authenticated %}
      <div class="notification-wrapper">
        <button class="notification-bell" id="notificationBell" type="button" aria-label="Notifications">
          <i class="bi bi-bell"></i>
          <span class="notification-badge" id="notificationBadge" style="display: none;"></span>
        </button>
        <div class="notification-dropdown" id="notificationDropdown">
          <div class="notification-header">
            <span class="notification-header-title">Documents NGSign</span>
            <div id="notificationBadges"></div>
          </div>
          <div id="notificationContent">
            <div class="notification-empty">Chargement...</div>
          </div>
        </div>
      </div>
      {% endif %}
      <div class="user-profile d-none d-md-flex">
```

- [ ] **Step 3: Commit**

```bash
git add invoice/templates/partials/base.html
git commit -m "feat: add notification bell markup and CSS to navbar"
```

---

### Task 5: Notification Bell — JavaScript (Polling, Rendering, Actions)

**Files:**
- Modify: `invoice/templates/partials/base.html`

- [ ] **Step 1: Add toast helper and notification JS**

In `invoice/templates/partials/base.html`, add the following script block **before** the `{% block scripts %}` tag (around line 719). Insert it after the existing `</script>` closing the sidebar toggle code:

```html
{% if user.is_authenticated %}
<script>
(function() {
  const bell = document.getElementById('notificationBell');
  const dropdown = document.getElementById('notificationDropdown');
  const badge = document.getElementById('notificationBadge');
  const content = document.getElementById('notificationContent');
  const badges = document.getElementById('notificationBadges');
  if (!bell) return;

  let pollInterval = null;

  // Toast helper — creates and shows a toast programmatically
  window.showToast = function(message, type) {
    type = type || 'info';
    let container = document.querySelector('.toast-container');
    if (!container) {
      const wrapper = document.createElement('div');
      wrapper.setAttribute('aria-live', 'polite');
      wrapper.setAttribute('aria-atomic', 'true');
      container = document.createElement('div');
      container.className = 'toast-container position-fixed top-0 end-0 p-3';
      wrapper.appendChild(container);
      document.body.appendChild(wrapper);
    }
    const iconMap = {
      success: 'bi-check-circle-fill',
      error: 'bi-x-circle-fill',
      warning: 'bi-exclamation-triangle-fill',
      info: 'bi-info-circle-fill',
    };
    const toastEl = document.createElement('div');
    toastEl.className = 'toast modern-toast align-items-center border-0 mb-2 text-white toast-' + type;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('data-bs-delay', '4000');
    toastEl.innerHTML =
      '<div class="d-flex">' +
        '<div class="toast-body"><i class="bi ' + (iconMap[type] || iconMap.info) + ' me-2"></i>' + message + '</div>' +
        '<button type="button" class="btn-close ' + (type !== 'warning' ? 'btn-close-white' : '') + ' me-2 m-auto" data-bs-dismiss="toast"></button>' +
      '</div>';
    container.appendChild(toastEl);
    new bootstrap.Toast(toastEl).show();
    toastEl.addEventListener('hidden.bs.toast', function() { toastEl.remove(); });
  };

  // Toggle dropdown
  bell.addEventListener('click', function(e) {
    e.stopPropagation();
    dropdown.classList.toggle('show');
  });

  // Close on outside click
  document.addEventListener('click', function(e) {
    if (!dropdown.contains(e.target) && e.target !== bell) {
      dropdown.classList.remove('show');
    }
  });

  function renderNotifications(data) {
    // Update badge
    if (data.total > 0) {
      badge.textContent = data.total;
      badge.style.display = 'flex';
    } else {
      badge.style.display = 'none';
    }

    // Header badges
    let badgeHtml = '';
    if (data.to_sign.length) badgeHtml += '<span style="background:#f39c12;color:#000;border-radius:10px;padding:2px 7px;font-size:0.65rem;margin-left:4px;">' + data.to_sign.length + '</span>';
    if (data.errors.length) badgeHtml += '<span style="background:#e74c3c;color:#fff;border-radius:10px;padding:2px 7px;font-size:0.65rem;margin-left:4px;">' + data.errors.length + '</span>';
    if (data.in_progress.length) badgeHtml += '<span style="background:#2ecc71;color:#000;border-radius:10px;padding:2px 7px;font-size:0.65rem;margin-left:4px;">' + data.in_progress.length + '</span>';
    badges.innerHTML = badgeHtml;

    if (data.total === 0) {
      content.innerHTML = '<div class="notification-empty">Aucun document en cours.</div>';
      stopPolling();
      return;
    }

    let html = '';

    if (data.to_sign.length) {
      html += '<div class="notification-group-label to-sign">A signer (' + data.to_sign.length + ')</div>';
      data.to_sign.forEach(function(item) {
        html += renderItem(item, 'sign');
      });
    }

    if (data.errors.length) {
      html += '<div class="notification-group-label errors">Erreurs (' + data.errors.length + ')</div>';
      data.errors.forEach(function(item) {
        html += renderItem(item, 'view');
      });
    }

    if (data.in_progress.length) {
      html += '<div class="notification-group-label in-progress">En cours (' + data.in_progress.length + ')</div>';
      data.in_progress.forEach(function(item) {
        if (item.status === 'SUBMITTING') {
          html += renderItem(item, 'spinner');
        } else {
          html += renderItem(item, 'check');
        }
      });
    }

    content.innerHTML = html;
    startPolling();
  }

  function renderItem(item, actionType) {
    let actionHtml = '';
    if (actionType === 'sign' && item.pds_url) {
      actionHtml = '<button class="notification-item-action sign" onclick="window.open(\'' + item.pds_url + '\', \'_blank\')">Signer</button>';
    } else if (actionType === 'view') {
      actionHtml = '<a href="' + item.detail_url + '" class="notification-item-action view" style="text-decoration:none;">Voir</a>';
    } else if (actionType === 'check') {
      actionHtml = '<button class="notification-item-action check" onclick="ngsignCheck(\'' + item.detail_url + '\')">Check</button>';
    } else if (actionType === 'spinner') {
      actionHtml = '<span class="notification-spinner"></span>';
    }

    return '<div class="notification-item">' +
      '<div class="notification-item-info">' +
        '<span class="notification-item-number">' + item.doc_number + '</span>' +
        '<span class="notification-item-client">' + item.client_name + '</span>' +
      '</div>' +
      actionHtml +
    '</div>';
  }

  window.fetchNotifications = function() {
    fetch('/api/ngsign/pending/')
      .then(function(r) { return r.json(); })
      .then(function(data) { renderNotifications(data); })
      .catch(function() {});
  };

  function startPolling() {
    if (pollInterval) return;
    pollInterval = setInterval(function() {
      if (document.hidden) return;
      fetchNotifications();
    }, 30000);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  // Pause/resume on tab visibility
  document.addEventListener('visibilitychange', function() {
    if (!document.hidden && badge.style.display !== 'none') {
      fetchNotifications();
    }
  });

  // Check button action from dropdown — navigates to detail page where user can run full check
  window.ngsignCheck = function(detailUrl) {
    window.location.href = detailUrl;
  };

  // Initial fetch
  document.addEventListener('DOMContentLoaded', function() {
    fetchNotifications();
  });
})();
</script>
{% endif %}
```

- [ ] **Step 2: Commit**

```bash
git add invoice/templates/partials/base.html
git commit -m "feat: add notification bell JS with polling, rendering, and toast helper"
```

---

### Task 6: Update Invoice Detail Template — Async Submit

**Files:**
- Modify: `invoice/templates/sales/invoice_detail_service.html`

- [ ] **Step 1: Replace the NGSign submit JS**

In `invoice/templates/sales/invoice_detail_service.html`, find the script block (lines 1101-1174). Replace the submit handler section (the `confirmBtn` click listener, lines 1106-1142) with:

```javascript
  confirmBtn.addEventListener('click', function () {
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Envoi en cours...';

    const csrfToken = document.cookie.split(';')
      .map(c => c.trim())
      .find(c => c.startsWith('csrftoken='));
    const token = csrfToken ? csrfToken.split('=')[1] : '';

    fetch('{% url "invoice-ngsign-submit" invoice.id %}', {
      method: 'POST',
      headers: { 'X-CSRFToken': token },
    })
      .then(r => r.json())
      .then(data => {
        const modal = bootstrap.Modal.getInstance(document.getElementById('ngsignSubmitModal'));
        if (modal) modal.hide();
        if (data.success) {
          showToast(data.message, 'success');
          if (typeof fetchNotifications === 'function') fetchNotifications();
        } else {
          showToast('Erreur : ' + data.error, 'error');
        }
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Soumettre';
      })
      .catch(err => {
        showToast('Erreur réseau : ' + err.message, 'error');
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Soumettre';
      });
  });
```

Key changes: removed `window.open(data.pds_url, '_blank')` and `location.reload()`, added `showToast()` and `fetchNotifications()` calls.

- [ ] **Step 2: Commit**

```bash
git add invoice/templates/sales/invoice_detail_service.html
git commit -m "feat: update invoice detail NGSign submit to async with toast feedback"
```

---

### Task 7: Update Avoir Detail Template — Async Submit

**Files:**
- Modify: `invoice/templates/sales/avoir_detail.html`

- [ ] **Step 1: Replace the NGSign submit JS**

In `invoice/templates/sales/avoir_detail.html`, find the submit handler (the `confirmBtn` click listener inside the script block). Replace it with the same async pattern:

```javascript
  confirmBtn.addEventListener('click', function () {
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Envoi en cours...';

    const csrfToken = document.cookie.split(';')
      .map(c => c.trim())
      .find(c => c.startsWith('csrftoken='));
    const token = csrfToken ? csrfToken.split('=')[1] : '';

    fetch('{% url "avoir-ngsign-submit" avoir.id %}', {
      method: 'POST',
      headers: { 'X-CSRFToken': token },
    })
      .then(r => r.json())
      .then(data => {
        const modal = bootstrap.Modal.getInstance(document.getElementById('ngsignSubmitModal'));
        if (modal) modal.hide();
        if (data.success) {
          showToast(data.message, 'success');
          if (typeof fetchNotifications === 'function') fetchNotifications();
        } else {
          showToast('Erreur : ' + data.error, 'error');
        }
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Soumettre';
      })
      .catch(err => {
        showToast('Erreur réseau : ' + err.message, 'error');
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Soumettre';
      });
  });
```

- [ ] **Step 2: Commit**

```bash
git add invoice/templates/sales/avoir_detail.html
git commit -m "feat: update avoir detail NGSign submit to async with toast feedback"
```

---

### Task 8: Manual Verification

- [ ] **Step 1: Start the dev server and test the bell**

Run:
```bash
cd invoice && python manage.py runserver
```

Open the app in the browser. The bell icon should appear in the navbar. If no documents have been submitted, the bell should have no badge and the dropdown should show "Aucun document en cours."

- [ ] **Step 2: Test async submission**

Navigate to an invoice detail page. Click the NGSign submit button. Verify:
1. Modal closes immediately
2. Toast appears: "Document soumis en arrière-plan."
3. Bell badge appears after a few seconds (or on next poll)
4. No redirect to PDS page

- [ ] **Step 3: Test notification dropdown**

Click the bell icon. Verify:
1. Dropdown shows grouped documents
2. "Signer" button opens PDS in new tab
3. "Voir" button navigates to detail page
4. Documents in SUBMITTING show spinner

- [ ] **Step 4: Test double-submit guard**

Click submit again while a document is still SUBMITTING. Verify error toast: "Soumission déjà en cours."

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete async NGSign submission and notification bell"
```
