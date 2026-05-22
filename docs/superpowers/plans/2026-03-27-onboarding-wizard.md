# Onboarding Setup Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 3-step setup wizard that hard-blocks new users until company info is entered, then shows a smart banner that disappears once settings are complete.

**Architecture:** A `SetupRequiredMiddleware` in `sales/middleware.py` redirects authenticated users with incomplete settings to `/setup/`. A `settings_context` context processor injects `settings_complete` into every template. The wizard view is a standard Django POST-redirect-GET multi-step form reusing the existing `SettingsForm`.

**Tech Stack:** Django middleware, Django context processors, Django session, Bootstrap 5, existing `SettingsForm`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `invoice/sales/middleware.py` | **Create** | `_settings_complete()`, `SetupRequiredMiddleware`, `settings_context` |
| `invoice/invoice/settings.py` | **Modify** | Register middleware + context processor |
| `invoice/sales/views.py` | **Modify** | Add `setup_wizard` view |
| `invoice/sales/urls.py` | **Modify** | Add `/setup/` URL |
| `invoice/templates/sales/setup_wizard.html` | **Create** | 3-step standalone wizard template |
| `invoice/templates/partials/base.html` | **Modify** | Add amber reminder banner after `</header>` |
| `tests/factories.py` | **Modify** | Add `emailAddress` to `SettingsFactory` |
| `tests/sales/test_setup_wizard.py` | **Create** | Tests for middleware, context processor, wizard view |

---

### Task 1: Update SettingsFactory and write failing tests

**Files:**
- Modify: `tests/factories.py`
- Create: `tests/sales/test_setup_wizard.py`

- [ ] **Step 1: Add `emailAddress` to `SettingsFactory`**

In `tests/factories.py`, find `class SettingsFactory` and add the missing field:

```python
class SettingsFactory(DjangoModelFactory):
    class Meta:
        model = 'sales.Settings'

    clientname = 'Test Company SARL'
    mf = '9876543XYZ000'
    adress = '123 Rue Test, Tunis'
    emailAddress = 'test@company.tn'
```

- [ ] **Step 2: Create `tests/sales/test_setup_wizard.py` with failing tests**

```python
import pytest
from unittest.mock import patch
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestSettingsComplete:
    def test_false_when_no_settings(self, tenant):
        from sales.middleware import _settings_complete
        assert _settings_complete() is False

    def test_false_when_email_missing(self, tenant):
        from sales.models import Settings
        from sales.middleware import _settings_complete
        with patch('sales.models._sync_ngsign_org'):
            Settings.objects.create(
                clientname='A', mf='123', adress='Tunis'
            )
        assert _settings_complete() is False

    def test_true_when_all_required_fields_set(self, tenant):
        from sales.models import Settings
        from sales.middleware import _settings_complete
        with patch('sales.models._sync_ngsign_org'):
            Settings.objects.create(
                clientname='A', mf='123', adress='Tunis',
                emailAddress='a@b.tn'
            )
        assert _settings_complete() is True


@pytest.mark.django_db(transaction=True)
class TestSetupRequiredMiddleware:
    def test_unauthenticated_not_redirected_to_setup(self, tenant):
        client = Client()
        resp = client.get('/dashboard/')
        assert resp.status_code == 302
        assert '/setup/' not in resp.url

    def test_incomplete_settings_redirects_to_setup(self, tenant, logged_in_client):
        resp = logged_in_client.get('/dashboard/')
        assert resp.status_code == 302
        assert resp.url == '/setup/'

    def test_complete_settings_passes_through(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get('/dashboard/')
        assert resp.status_code == 200

    def test_setup_url_is_exempt(self, tenant, logged_in_client):
        resp = logged_in_client.get('/setup/')
        assert resp.status_code in (200, 302)
        # Must not redirect to /setup/ from /setup/ (infinite loop)
        if resp.status_code == 302:
            assert resp.url != '/setup/'

    def test_api_url_is_exempt(self, tenant, logged_in_client):
        resp = logged_in_client.get('/api/ngsign/pending/')
        # API responses should never be redirected to setup page
        assert resp.status_code != 302 or '/setup/' not in (resp.url or '')

    def test_logout_url_is_exempt(self, tenant, logged_in_client):
        resp = logged_in_client.get('/logout')
        if resp.status_code == 302:
            assert '/setup/' not in resp.url


@pytest.mark.django_db(transaction=True)
class TestSettingsContextProcessor:
    def test_settings_complete_false_when_incomplete(self, tenant, logged_in_client):
        resp = logged_in_client.get('/setup/')
        assert resp.context['settings_complete'] is False

    def test_settings_complete_true_when_complete(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get('/setup/')
        # Complete settings → wizard redirects to dashboard
        assert resp.status_code == 302


@pytest.mark.django_db(transaction=True)
class TestSetupWizardView:
    def test_redirects_to_dashboard_when_already_complete(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get('/setup/')
        assert resp.status_code == 302
        assert resp.url == reverse('dashboard')

    def test_get_step1_renders(self, tenant, logged_in_client):
        resp = logged_in_client.get('/setup/')
        assert resp.status_code == 200
        assert resp.context['step'] == 1

    def test_post_step1_valid_advances_to_step2(self, tenant, logged_in_client):
        with patch('sales.models._sync_ngsign_org'):
            resp = logged_in_client.post('/setup/', {
                'action': 'next',
                'clientname': 'My Company',
                'emailAddress': 'contact@company.tn',
                'adress': '123 Rue Test, Tunis',
                'status': 'Person Morale',
                'phone': '',
            })
        assert resp.status_code == 302
        assert resp.url == '/setup/'
        resp2 = logged_in_client.get('/setup/')
        assert resp2.context['step'] == 2

    def test_post_step1_missing_required_rerenders(self, tenant, logged_in_client):
        resp = logged_in_client.post('/setup/', {
            'action': 'next',
            'clientname': '',
            'emailAddress': 'contact@company.tn',
            'adress': '123 Rue Test, Tunis',
        })
        assert resp.status_code == 200
        assert resp.context['step'] == 1

    def test_post_step2_valid_advances_to_step3(self, tenant, logged_in_client):
        from sales.models import Settings
        session = logged_in_client.session
        session['setup_step'] = 2
        session.save()
        with patch('sales.models._sync_ngsign_org'):
            Settings.objects.create(
                clientname='A', emailAddress='a@b.tn', adress='Tunis'
            )
            resp = logged_in_client.post('/setup/', {
                'action': 'next',
                'mf': '1234567ABC000',
                'tva': '19.00',
                'dt': '1.000',
                'default_retenu_rate': '',
            })
        assert resp.status_code == 302
        resp2 = logged_in_client.get('/setup/')
        assert resp2.context['step'] == 3

    def test_post_step3_skip_redirects_to_dashboard(self, tenant, logged_in_client):
        session = logged_in_client.session
        session['setup_step'] = 3
        session.save()
        resp = logged_in_client.post('/setup/', {'action': 'skip'})
        assert resp.status_code == 302
        assert resp.url == reverse('dashboard')
```

- [ ] **Step 3: Run tests to confirm they all fail (middleware not yet created)**

```
cd invoice
python -m pytest ../tests/sales/test_setup_wizard.py --co -q
python -m pytest ../tests/sales/test_setup_wizard.py -q 2>&1 | tail -5
```

Expected: collection succeeds, all tests ERROR/FAIL with `ModuleNotFoundError: No module named 'sales.middleware'`

---

### Task 2: Create `sales/middleware.py` and register it

**Files:**
- Create: `invoice/sales/middleware.py`
- Modify: `invoice/invoice/settings.py`

- [ ] **Step 1: Create `invoice/sales/middleware.py`**

```python
from django.shortcuts import redirect

EXEMPT_PREFIXES = ('/', '/setup/', '/logout', '/admin/', '/api/')


def _settings_complete():
    """Returns True if the current tenant's Settings has all required fields."""
    from sales.models import Settings
    s = Settings.get_cached()
    return bool(s and s.clientname and s.mf and s.adress and s.emailAddress)


class SetupRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            path = request.path
            exempt = path == '/' or any(
                path.startswith(p) for p in ('/setup/', '/logout', '/admin/', '/api/')
            )
            if not exempt and not _settings_complete():
                return redirect('setup_wizard')
        return self.get_response(request)


def settings_context(request):
    """Injects settings_complete into every template context."""
    if not request.user.is_authenticated:
        return {}
    return {'settings_complete': _settings_complete()}
```

- [ ] **Step 2: Register middleware and context processor in `invoice/invoice/settings.py`**

Find the `MIDDLEWARE` list. Add `'sales.middleware.SetupRequiredMiddleware'` immediately after `'tenants.middleware.SessionTenantMiddleware'`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ... (keep existing entries)
    'tenants.middleware.SessionTenantMiddleware',
    'sales.middleware.SetupRequiredMiddleware',   # ← add this line
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

Find the `context_processors` list inside `TEMPLATES[0]['OPTIONS']`. Add `'sales.middleware.settings_context'`:

```python
'context_processors': [
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'sales.middleware.settings_context',   # ← add this line
],
```

- [ ] **Step 3: Run middleware tests to verify they pass**

```
cd invoice
python -m pytest ../tests/sales/test_setup_wizard.py::TestSettingsComplete ../tests/sales/test_setup_wizard.py::TestSetupRequiredMiddleware -v 2>&1 | tail -20
```

Expected: `TestSettingsComplete` all pass. `TestSetupRequiredMiddleware` tests may partially fail (wizard view not yet implemented). `test_incomplete_settings_redirects_to_setup` and `test_complete_settings_passes_through` should pass. `test_setup_url_is_exempt` will fail (500 because setup_wizard view doesn't exist yet).

- [ ] **Step 4: Commit**

```bash
git add invoice/sales/middleware.py invoice/invoice/settings.py tests/factories.py tests/sales/test_setup_wizard.py
git commit -m "feat: add SetupRequiredMiddleware, settings_context, and wizard tests"
```

---

### Task 3: Implement `setup_wizard` view and URL

**Files:**
- Modify: `invoice/sales/views.py`
- Modify: `invoice/sales/urls.py`

- [ ] **Step 1: Add `setup_wizard` to `invoice/sales/views.py`**

Add this function at the end of `views.py` (after the last view, before any trailing code):

```python
@login_required
def setup_wizard(request):
    """Multi-step setup wizard for first-time company configuration."""
    import base64 as _b64
    from sales.forms import SettingsForm
    from sales.middleware import _settings_complete

    STEP_FIELDS = {
        1: ['clientname', 'status', 'emailAddress', 'phone', 'adress'],
        2: ['mf', 'tva', 'dt', 'default_retenu_rate'],
        3: ['rib', 'logo_upload'],
    }
    STEP_REQUIRED = {
        1: ['clientname', 'emailAddress', 'adress'],
        2: ['mf'],
        3: [],
    }

    if _settings_complete():
        return redirect('dashboard')

    step = request.session.get('setup_step', 1)
    if step not in STEP_FIELDS:
        step = 1

    settings_obj = Settings.get_cached()

    if request.method == 'POST':
        action = request.POST.get('action', 'next')

        if action == 'skip' and step == 3:
            request.session.pop('setup_step', None)
            return redirect('dashboard')

        if step == 3:
            form = SettingsForm(request.POST, request.FILES, instance=settings_obj)
        else:
            form = SettingsForm(request.POST, instance=settings_obj)

        # Restrict to this step's fields and set required flags
        for fname in list(form.fields.keys()):
            if fname not in STEP_FIELDS[step]:
                del form.fields[fname]
        for fname in form.fields:
            form.fields[fname].required = fname in STEP_REQUIRED[step]

        if form.is_valid():
            obj = form.save(commit=False)

            if step == 3:
                logo_file = request.FILES.get('logo_upload')
                if logo_file:
                    if logo_file.size > 2 * 1024 * 1024:
                        form.add_error('logo_upload', 'Le logo ne doit pas dépasser 2 Mo.')
                        return render(request, 'sales/setup_wizard.html', {'form': form, 'step': step})
                    raw = logo_file.read()
                    encoded = _b64.b64encode(raw).decode('utf-8')
                    obj.clientLogo = f'data:{logo_file.content_type};base64,{encoded}'
                elif settings_obj:
                    obj.clientLogo = settings_obj.clientLogo

            obj.save()

            if step == 3:
                request.session.pop('setup_step', None)
                return redirect('dashboard')
            request.session['setup_step'] = step + 1
            return redirect('setup_wizard')

    else:
        form = SettingsForm(instance=settings_obj)
        for fname in list(form.fields.keys()):
            if fname not in STEP_FIELDS[step]:
                del form.fields[fname]
        for fname in form.fields:
            form.fields[fname].required = fname in STEP_REQUIRED[step]

    return render(request, 'sales/setup_wizard.html', {'form': form, 'step': step})
```

`Settings` is already imported at the top of `views.py`. Confirm with:
```bash
grep "from .models import\|from sales.models import" invoice/sales/views.py | head -3
```

- [ ] **Step 2: Add the URL to `invoice/sales/urls.py`**

Find the imports at the top of `urls.py` and add `setup_wizard` to the import from views. Then add the URL pattern:

```python
# In the imports section, add setup_wizard to the existing views import:
from .views import (..., setup_wizard)

# In urlpatterns, add:
path('setup/', setup_wizard, name='setup_wizard'),
```

- [ ] **Step 3: Run wizard view tests**

```
cd invoice
python -m pytest ../tests/sales/test_setup_wizard.py -v 2>&1 | tail -25
```

Expected: All `TestSetupWizardView` tests pass except any that render a template (template doesn't exist yet — those will give `TemplateDoesNotExist` error). `test_redirects_to_dashboard_when_already_complete`, `test_post_step3_skip_redirects_to_dashboard` should pass. GET tests will fail with `TemplateDoesNotExist`.

- [ ] **Step 4: Commit**

```bash
git add invoice/sales/views.py invoice/sales/urls.py
git commit -m "feat: add setup_wizard view and URL"
```

---

### Task 4: Create the wizard template

**Files:**
- Create: `invoice/templates/sales/setup_wizard.html`

- [ ] **Step 1: Create `invoice/templates/sales/setup_wizard.html`**

```html
{% load static %}
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Configuration — Swift Invoice</title>
  <link rel="shortcut icon" href="{% static 'assets/img/logo1.png' %}">
  <link href="{% static 'assets/css/bootstrap.min.css' %}" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <style>
    body { background: #0f172a; color: #f1f5f9; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: 'Segoe UI', sans-serif; }
    .wizard-brand { font-size: 0.75rem; letter-spacing: 2px; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
    .wizard-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 4px; }
    .wizard-subtitle { font-size: 0.875rem; color: #64748b; margin-bottom: 2rem; }
    .wizard-card { background: #1e293b; border-radius: 12px; padding: 2rem; width: 100%; max-width: 520px; }
    .step-title { font-size: 0.95rem; font-weight: 600; color: #f59e0b; margin-bottom: 1.25rem; }
    .progress-row { display: flex; align-items: center; gap: 8px; margin-bottom: 1.5rem; }
    .step-circle { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; flex-shrink: 0; }
    .step-circle.active { background: #3b82f6; color: #fff; }
    .step-circle.done { background: #22c55e; color: #fff; }
    .step-circle.pending { background: #334155; color: #64748b; }
    .step-line { flex: 1; height: 3px; border-radius: 2px; }
    .step-line.done { background: #22c55e; }
    .step-line.pending { background: #334155; }
    .form-label { font-size: 0.8rem; color: #94a3b8; margin-bottom: 4px; }
    .form-control, .form-select { background: #0f172a; border: 1px solid #334155; color: #f1f5f9; border-radius: 6px; }
    .form-control:focus, .form-select:focus { background: #0f172a; color: #f1f5f9; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.2); }
    .form-control::placeholder { color: #475569; }
    .required-star { color: #f87171; margin-left: 2px; }
    .invalid-feedback { font-size: 0.75rem; }
    .btn-primary { background: #3b82f6; border-color: #3b82f6; }
    .btn-primary:hover { background: #2563eb; border-color: #2563eb; }
    .btn-secondary-outline { background: transparent; border: 1px solid #475569; color: #94a3b8; }
    .btn-secondary-outline:hover { border-color: #64748b; color: #cbd5e1; }
  </style>
</head>
<body>
  <div class="text-center mb-2">
    <div class="wizard-brand">Swift Invoice</div>
    {% if step == 1 %}
    <div class="wizard-title">Bienvenue 👋</div>
    <div class="wizard-subtitle">Configurez votre entreprise pour commencer</div>
    {% endif %}
  </div>

  <div class="wizard-card">
    <!-- Progress -->
    <div class="progress-row">
      <div class="step-circle {% if step == 1 %}active{% else %}done{% endif %}">
        {% if step > 1 %}<i class="bi bi-check"></i>{% else %}1{% endif %}
      </div>
      <div class="step-line {% if step > 1 %}done{% else %}pending{% endif %}"></div>
      <div class="step-circle {% if step == 2 %}active{% elif step > 2 %}done{% else %}pending{% endif %}">
        {% if step > 2 %}<i class="bi bi-check"></i>{% else %}2{% endif %}
      </div>
      <div class="step-line {% if step > 2 %}done{% else %}pending{% endif %}"></div>
      <div class="step-circle {% if step == 3 %}active{% else %}pending{% endif %}">3</div>
      <span style="font-size:0.75rem;color:#64748b;margin-left:8px;white-space:nowrap;">Étape {{ step }} / 3</span>
    </div>

    <!-- Step title -->
    <div class="step-title">
      {% if step == 1 %}🏢 Informations entreprise
      {% elif step == 2 %}🧾 Informations fiscales
      {% else %}🏦 Banque &amp; Logo <span style="font-size:0.75rem;font-weight:400;color:#64748b;">(optionnel)</span>
      {% endif %}
    </div>

    <!-- Form -->
    <form method="post" enctype="multipart/form-data" novalidate>
      {% csrf_token %}
      <div class="row g-3">
        {% for field in form %}
        <div class="{% if field.field.widget.input_type == 'textarea' %}col-12{% else %}col-md-6{% endif %}">
          <label class="form-label" for="{{ field.id_for_label }}">
            {{ field.label }}
            {% if field.field.required %}<span class="required-star">*</span>{% endif %}
          </label>
          {{ field }}
          {% if field.errors %}
          <div class="invalid-feedback d-block">{{ field.errors|join:", " }}</div>
          {% endif %}
        </div>
        {% endfor %}
      </div>

      <div class="d-flex justify-content-end gap-2 mt-4">
        {% if step == 3 %}
        <button type="submit" name="action" value="skip" class="btn btn-secondary-outline btn-sm px-4">
          Passer
        </button>
        <button type="submit" name="action" value="next" class="btn btn-primary btn-sm px-4">
          Terminer <i class="bi bi-check2"></i>
        </button>
        {% else %}
        <button type="submit" name="action" value="next" class="btn btn-primary btn-sm px-4">
          Suivant <i class="bi bi-arrow-right"></i>
        </button>
        {% endif %}
      </div>
    </form>
  </div>

  <script src="{% static 'assets/js/bootstrap.bundle.min.js' %}"></script>
</body>
</html>
```

- [ ] **Step 2: Run full wizard tests**

```
cd invoice
python -m pytest ../tests/sales/test_setup_wizard.py -v 2>&1 | tail -25
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add invoice/templates/sales/setup_wizard.html
git commit -m "feat: add setup wizard template"
```

---

### Task 5: Add reminder banner to `base.html`

**Files:**
- Modify: `invoice/templates/partials/base.html`

- [ ] **Step 1: Insert the banner after `</header>` in `base.html`**

Find the line `  </header>` (around line 744) and insert immediately after it:

```html
  </header>
  {% if user.is_authenticated and not settings_complete %}
  <div style="background:#f59e0b;padding:9px 16px;display:flex;align-items:center;gap:10px;">
    <i class="bi bi-exclamation-triangle-fill" style="color:#0f172a;font-size:0.9rem;"></i>
    <span style="font-size:0.85rem;color:#0f172a;font-weight:500;">Votre entreprise n'est pas encore configurée.</span>
    <a href="{% url 'setup_wizard' %}" style="font-size:0.85rem;color:#0f172a;font-weight:700;text-decoration:underline;">Compléter la configuration →</a>
  </div>
  {% endif %}
```

- [ ] **Step 2: Verify banner renders in existing view test**

```
cd invoice
python -m pytest ../tests/sales/test_settings_views.py -v 2>&1 | tail -10
```

Expected: All settings view tests still pass.

- [ ] **Step 3: Commit**

```bash
git add invoice/templates/partials/base.html
git commit -m "feat: add setup reminder banner to base template"
```

---

### Task 6: Run full test suite and verify no regressions

**Files:** None

- [ ] **Step 1: Run full suite**

```
cd invoice
python -m pytest ../tests/ -v --tb=short 2>&1
```

Expected: All tests pass (or same count as before + new wizard tests). Look specifically for any tests that now redirect to `/setup/` unexpectedly — those would indicate a view test that uses `logged_in_client` without the `seller` fixture.

- [ ] **Step 2: If any tests fail with `302` to `/setup/`, fix them**

Any test that:
- Uses `logged_in_client` without `seller`
- Calls a non-API, non-exempt URL
- Asserts `status_code == 200`

...needs `seller` added to its fixture list. Example fix:

```python
# Before:
def test_some_view(self, tenant, logged_in_client):

# After:
def test_some_view(self, tenant, seller, logged_in_client):
```

- [ ] **Step 3: Commit any fixes**

```bash
git add -p  # stage only the test fixture fixes
git commit -m "fix: add seller fixture to view tests affected by setup middleware"
```

- [ ] **Step 4: Final run — confirm all green**

```
cd invoice
python -m pytest ../tests/ -q 2>&1 | tail -5
```

Expected: `N passed in X.XXs`
