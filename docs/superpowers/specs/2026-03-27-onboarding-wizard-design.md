# Onboarding Setup Wizard Design

**Date:** 2026-03-27
**Branch:** feature/onboarding-wizard
**Status:** Approved

---

## Goal

Guide new users to enter their company information before using the app, reducing usage errors and credential complications (e.g. NGSign, Elfatoura submissions that require a valid MF).

---

## Behaviour Summary

| Situation | Behaviour |
|---|---|
| First login, settings empty | Hard redirect to `/setup/` — cannot access any other page |
| Settings still incomplete on subsequent visits | Amber banner in navbar — persistent, links to `/setup/` |
| Settings complete | Banner disappears automatically — no manual dismiss needed |
| User navigates directly to another URL while incomplete | Middleware redirects to `/setup/` |

**"Settings complete"** is defined as: a `Settings` object exists with `clientname`, `mf`, `adress`, and `emailAddress` all non-empty. Logo, RIB, phone, and tax rates are collected in the wizard but are not blockers.

---

## Wizard Structure

**URL:** `/setup/` — dedicated full page, not a modal.

**3 steps:**

| Step | Title | Fields | Required to advance |
|---|---|---|---|
| 1 | Entreprise | `clientname`, `status`, `emailAddress`, `phone`, `adress` | `clientname`, `emailAddress`, `adress` |
| 2 | Fiscal | `mf`, `tva`, `dt`, `default_retenu_rate` | `mf` |
| 3 | Banque & Logo | `rib`, `clientLogo` | None — skippable |

Completing Step 2 satisfies the "settings complete" condition. Step 3 is shown but has a **"Passer"** button that skips to dashboard without saving.

---

## Architecture

### 1. Shared helper — `_settings_complete()`

A single function in `sales/middleware.py`:

```python
def _settings_complete():
    from sales.models import Settings
    s = Settings.get_cached()
    return bool(s and s.clientname and s.mf and s.adress and s.emailAddress)
```

Used by both the middleware and the context processor — one place to change the definition.

### 2. `SetupRequiredMiddleware` (`sales/middleware.py`)

- Position in `MIDDLEWARE`: immediately after `SessionTenantMiddleware` (tenant schema must be set first)
- Only runs for authenticated users
- Exempt paths: `/`, `/setup/`, `/logout/`, `/admin/`
- On every non-exempt request: calls `_settings_complete()` → if `False`, returns `redirect('setup_wizard')`
- Uses `Settings.get_cached()` — single cache lookup, no extra DB hit on hot path

### 3. `settings_context` context processor (`sales/middleware.py`)

```python
def settings_context(request):
    if not request.user.is_authenticated:
        return {}
    return {'settings_complete': _settings_complete()}
```

Registered in `TEMPLATES[0]['OPTIONS']['context_processors']` in `invoice/settings.py`. Injects `settings_complete` into every template rendered while authenticated.

### 4. `setup_wizard` view (`sales/views.py`)

- Decorator: `@login_required`
- Methods: GET and POST
- Session key `setup_step` (int, 1–3) tracks current step; defaults to 1

**GET:** renders `sales/setup_wizard.html` with the current step number and the appropriate field subset.

**POST:**
- Reads `action` from POST data (`'next'` or `'skip'`)
- If `action == 'skip'` (Step 3 only): clears `setup_step`, redirects to `dashboard`
- Otherwise: instantiates `SettingsForm` with only that step's fields, validates
  - Valid: saves (`Settings.objects.update_or_create` on the single Settings record), advances `setup_step`, redirects to `/setup/` (PRG pattern)
  - Invalid: re-renders with errors
- After saving Step 3 (or skip): clears `setup_step` from session, redirects to `dashboard`

**Settings object lifecycle:** `get_or_create` on first POST so the same object is updated across all 3 steps.

### 5. URL

```python
path('setup/', setup_wizard, name='setup_wizard'),
```

Added to `sales/urls.py`. The middleware exempt list uses the string `/setup/` (not `reverse()`) to avoid circular import issues at middleware init time.

---

## Templates

### `templates/sales/setup_wizard.html`

- Extends nothing — standalone full-page template (dark theme, matching existing login page style)
- Brand header: "Swift Invoice" wordmark
- Welcome heading + subtitle (only on Step 1)
- **Progress indicator:** numbered circles (1, 2, 3) connected by lines — active step filled blue, future steps grey
- **Form card:** amber step title (e.g. "🏢 Informations entreprise"), 2-column field grid, required fields marked with `*`
- **Footer buttons:**
  - Steps 1–2: "Suivant →" (submit)
  - Step 3: "Terminer" (submit) + "Passer" (skip, secondary style)
- Form errors shown inline under each field

### `templates/partials/base.html` — reminder banner

Inserted immediately after the `<nav>` element, inside the `{% if user.is_authenticated %}` block:

```html
{% if not settings_complete %}
<div class="setup-banner">
  ⚠️ Votre entreprise n'est pas encore configurée.
  <a href="{% url 'setup_wizard' %}">Compléter la configuration →</a>
</div>
{% endif %}
```

Styled amber (`#f59e0b` background, dark text). No close button — disappears automatically once settings are complete.

---

## Django Settings Changes (`invoice/settings.py`)

```python
MIDDLEWARE = [
    ...
    'tenants.middleware.SessionTenantMiddleware',
    'sales.middleware.SetupRequiredMiddleware',   # ← add after tenant middleware
    ...
]

TEMPLATES = [{
    ...
    'OPTIONS': {
        'context_processors': [
            ...
            'sales.middleware.settings_context',   # ← add
        ],
    },
}]
```

---

## Files to Create / Modify

| File | Change |
|---|---|
| `sales/middleware.py` | **Create** — `_settings_complete()`, `SetupRequiredMiddleware`, `settings_context` |
| `sales/views.py` | **Add** `setup_wizard` view |
| `sales/urls.py` | **Add** `/setup/` URL |
| `templates/sales/setup_wizard.html` | **Create** — 3-step wizard template |
| `templates/partials/base.html` | **Add** reminder banner after `<nav>` |
| `invoice/settings.py` | **Update** `MIDDLEWARE` and `context_processors` |

---

## Edge Cases

| Case | Handling |
|---|---|
| User visits `/setup/` when already complete | View redirects to `dashboard` immediately |
| Superuser with no Settings | Middleware applies equally — superusers must complete setup too |
| Step session expires / out of range | View defaults `setup_step` to 1 |
| `Settings.get_cached()` called before schema set | Middleware runs after `SessionTenantMiddleware`, so schema is always set |
| Unauthenticated user | Middleware skips entirely; context processor returns `{}` |
