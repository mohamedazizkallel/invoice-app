# Notification Clearing System — Design Spec

## Overview

Add read/dismiss functionality to the NGSign notification bell, an error detail modal, and a dedicated notifications page. Built on top of the existing `ngsign_pending_api` system without changing the `GovInvoice` model.

## 1. Data Model

A single new model in `sales/models.py`:

```python
class NotificationState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    gov_invoice = models.ForeignKey('gov.GovInvoice', on_delete=models.CASCADE)
    status_snapshot = models.CharField(max_length=50)  # matches GovInvoice.ngsign_status max_length
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'gov_invoice')
```

When a `GovInvoice` is deleted, CASCADE removes the associated `NotificationState` — the notification simply disappears.

All read/dismiss state is per-user. User A's dismissals do not affect User B's view.

### Status-change reappearance logic

When the API builds the notification list, for each `GovInvoice` it checks the corresponding `NotificationState` for `request.user`:

- **Dismissed:** If `is_dismissed=True` and `gov_invoice.ngsign_status == status_snapshot` → exclude from results. If status differs → notification reappears (reset `is_dismissed=False`, `dismissed_at=None`).
- **Read:** If `is_read=True` and `gov_invoice.ngsign_status == status_snapshot` → item is read. If status differs → item becomes unread again (reset `is_read=False`).
- **No state:** Item is unread and visible.

Note: The existing stale-detection mutation in `ngsign_pending_api` (changing `SUBMITTING` → `ERROR` after 60s) constitutes a status change that will trigger notification reappearance for any user who dismissed/read the item while it was `SUBMITTING`.

## 2. API Changes

### Modified endpoint

**`GET /api/ngsign/pending/`** — existing endpoint, modified response:

Each item gains:
- `is_read` (bool) — whether the user has read this notification

Response-level additions:
- `unread_count` (int) — number of unread, non-dismissed items (drives the badge)
- `total` (int) — kept for backward compatibility, now counts non-dismissed items only

Dismissed items with matching status are excluded from results entirely.

### New endpoints

| Endpoint | Method | Decorators | Purpose |
|---|---|---|---|
| `api/ngsign/notifications/read/` | POST | `@login_required`, `@require_POST` | Mark all as read. Creates/updates `NotificationState` for each non-dismissed, non-terminal `GovInvoice` with `is_read=True` and current `status_snapshot`. Returns `{"ok": true, "unread_count": 0}`. |
| `api/ngsign/notifications/<int:gov_invoice_id>/dismiss/` | POST | `@login_required`, `@require_POST` | Dismiss a single notification by `GovInvoice.id`. Uses `update_or_create(user=request.user, gov_invoice_id=gov_invoice_id)` to set `is_dismissed=True`, `status_snapshot=current status`, `dismissed_at=now()`. Returns `{"ok": true}`. |
| `notifications/` | GET | `@login_required` | Notifications history page (HTML). |

"Active" for mark-all-read means: all `GovInvoice` records with non-terminal `ngsign_status` (same filter as the bell API) that are not currently dismissed with a matching status.

## 3. Bell Dropdown UI Changes

### Header area
- "Documents NGSign" title stays
- Add **"Tout lire"** link-button on the right side of the header (marks all as read)
- Add **"Voir tout"** link at the bottom of the dropdown → navigates to `/notifications/`

### Badge
- Badge now shows `unread_count` instead of `total`
- Badge hides when `unread_count == 0`

### Per-item changes
- Add a small **dismiss button** (× icon) on each notification item, positioned to the right of the existing action button
- Read items get **muted styling** (`opacity: 0.6`) to distinguish from unread
- Error items get a **"Détails"** button that opens a modal with the error text

### Error detail modal
- Reusable Bootstrap modal, shared across all error items
- **Title:** `{doc_type} {doc_number} — {client_name}`
- **Body:** Contents of the `notes` field rendered via `textContent` (not `innerHTML`) to prevent XSS from external NGSign error messages
- **Footer:** Single "Fermer" button
- Modal content populated dynamically via JS when "Détails" is clicked

### Behavior
- "Tout lire" → POST `/api/ngsign/notifications/read/` → update badge to 0 immediately from response → re-fetch full list
- × button → POST `/api/ngsign/notifications/{gov_invoice_id}/dismiss/` → item fades out → re-fetch
- "Détails" → populate and show Bootstrap modal (no server call)
- Polling continues as before (30s interval), respects read/dismissed state
- Race condition note: if a poll response arrives between a dismiss POST and re-fetch, the dismissed item may briefly reappear. This is acceptable — the next re-fetch corrects it.

## 4. Notifications Page

**URL:** `/notifications/`
**Template:** `invoice/templates/notifications.html` (extends `partials/base.html`)

### Content
- Page title: "Notifications"
- Filter tabs: "Tous", "A signer", "Erreurs", "En cours", "Terminés"
- Paginated: 50 items per page
- Table/list showing all `GovInvoice` records including terminal statuses
- Columns: Status badge, Document type + number, Client, Date, Notes (truncated), Actions
- Actions per row: "Voir" link (to document detail), Dismiss button, "Détails" button for errors
- "Tout lire" button at the top
- Read/dismissed items shown with muted styling
- Matches existing app styling (modern look consistent with client/invoice list pages)

### Status-to-tab mapping

| Tab | Statuses |
|---|---|
| Tous | All statuses |
| A signer | `CREATED`, `CONFIGURED` |
| Erreurs | `ERROR`, `TTN_REJECTED`, `TTN_NOTTRANSFERED` |
| En cours | `SUBMITTING`, `SIGNED`, `MIXED` |
| Terminés | `TTN_SIGNED`, `TTN_TRANSFERED`, `CANCELLED` |

### Data source
The page view queries `GovInvoice` directly (not limited to non-terminal statuses like the bell API) and left-joins `NotificationState` for `request.user` to show read/dismissed state.

## 5. Files Changed

| File | Change |
|---|---|
| `sales/models.py` | Add `NotificationState` model |
| `sales/migrations/XXXX_notificationstate.py` | New migration |
| `sales/views.py` | Modify `ngsign_pending_api`, add `mark_all_read`, `dismiss_notification`, `notifications_page` views |
| `sales/urls.py` | Add 3 new URL patterns |
| `templates/partials/base.html` | Update bell dropdown HTML, add error modal, update JS for dismiss/read/modal, minor CSS additions |
| `templates/notifications.html` | New template for notifications page |

## 6. What Does NOT Change

- `GovInvoice` model — no modifications
- `gov/` app — untouched
- No signals or hooks needed
- Existing polling mechanism stays the same
- Existing NGSign submission/check flows unchanged
