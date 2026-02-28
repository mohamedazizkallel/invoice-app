# Multi-Tenancy Plan

## Current State
Single-tenant app. All users share the same data — no isolation between companies.
PostgreSQL in production, SQLite in dev.

---

## Option A — `django-tenants` (PostgreSQL schema-per-tenant) ✅ Recommended

Each tenant gets a dedicated PostgreSQL schema. Data is isolated at the database level.
No changes needed to existing models or view querysets.

### How it works
- A `Tenant` row is created for each company.
- Django routes the request to the correct schema based on the subdomain (e.g. `company1.app.com`).
- All queries (`Invoice.objects.all()`, etc.) automatically hit only that tenant's schema.

### Steps

**1. Install package**
```
pip install django-tenants
```

**2. Create a `tenants` app**
```python
# tenants/models.py
from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    paid_until = models.DateField()
    on_trial = models.BooleanField()
    auto_create_schema = True

class Domain(DomainMixin):
    pass
```

**3. Update settings.py**
```python
INSTALLED_APPS = [
    'django_tenants',
    'tenants',                        # new app
    # shared apps above, tenant apps below
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'sales',
    'payment',
    'gov',
    'crispy_forms',
    'crispy_bootstrap5',
]

SHARED_APPS = [
    'django_tenants',
    'tenants',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
]

TENANT_APPS = [
    'sales',
    'payment',
    'gov',
]

TENANT_MODEL = 'tenants.Tenant'
TENANT_DOMAIN_MODEL = 'tenants.Domain'

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',  # swap default engine
        'NAME': env('POSTGRES_DB'),
        'USER': env('POSTGRES_USER'),
        'PASSWORD': env('POSTGRES_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', default='5432'),
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',  # must be first
    'django.middleware.security.SecurityMiddleware',
    # ... rest unchanged
]
```

**4. Migrate**
```bash
python manage.py migrate_schemas --shared   # sets up public schema
python manage.py migrate_schemas            # runs tenant migrations
```

**5. Create the first tenant (via shell)**
```python
from tenants.models import Tenant, Domain

tenant = Tenant(schema_name='company1', name='Company One', paid_until='2026-12-31', on_trial=False)
tenant.save()

domain = Domain(domain='company1.yourdomain.com', tenant=tenant, is_primary=True)
domain.save()
```

**6. Fix `Settings.get_cached()` cache key**
The current caching uses a bare key `'company_settings'`. Under multi-tenancy this would
bleed across tenants. Update it to include the schema name:
```python
from django.db import connection

cache_key = f'company_settings_{connection.schema_name}'
```

**7. Scope media files**
Company logos are stored in `/media/`. Add a per-tenant upload path:
```python
def tenant_logo_path(instance, filename):
    from django.db import connection
    return f'logos/{connection.schema_name}/{filename}'

clientLogo = models.TextField(...)  # already base64, no change needed
```

**8. Dev environment**
SQLite must be dropped. Run a local Postgres instance:
```bash
docker run -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=invoice -p 5432:5432 postgres
```
Update your local `.env` accordingly.

### What does NOT change
- All models (Client, Invoice, Supplier, Service, etc.) — untouched
- All 83 URL patterns — untouched
- All views and querysets — untouched
- All templates — untouched
- Sequential IDs (FV-###-YEAR) — automatically isolated per schema

### Effort estimate
| Task | Time |
|---|---|
| Package + settings | 30 min |
| Tenant + Domain models | 1 hour |
| Re-run migrations | 1–2 hours |
| URL/subdomain routing + deploy config | 2–3 hours |
| Fix Settings cache key | 30 min |
| Drop SQLite, local Postgres setup | 1 hour |
| **Total** | **~2–3 days** |

---

## Option B — Row-level tenancy (no library)

Add a `tenant` foreign key to every model and filter every queryset manually.

### Steps

**1. Create Tenant model**
```python
class Tenant(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
```

**2. Add `tenant` FK to every model**
Models that need updating: `Client`, `Invoice`, `Supplier`, `Service`, `Supply`,
`Purchase`, `CreditNote`, `Settings`, `InvoiceService`, `PurchaseLine`,
`Retenu`, `InvoiceRetenu`, `PurchaseRetenu`, `GovInvoice` — **14 models, 14 migrations**

**3. Tenant middleware**
```python
class TenantMiddleware:
    def __call__(self, request):
        subdomain = request.get_host().split('.')[0]
        request.tenant = Tenant.objects.get(slug=subdomain)
        return self.get_response(request)
```

**4. Update every queryset in views.py (81KB)**
Every `objects.all()` / `objects.filter()` needs `.filter(tenant=request.tenant)`.
Approximately 150+ querysets across sales/views.py, payment/views.py, gov/views.py.

**5. Update every create/save to stamp the tenant**
Every form save needs `instance.tenant = request.tenant` before `commit=True`.

**6. Update `Settings.objects.first()`**
Used in ~30 places — all need `.filter(tenant=request.tenant).first()`.

**7. Custom model managers (recommended to reduce risk)**
```python
class TenantManager(models.Manager):
    def get_queryset(self):
        from threading import local
        _thread_locals = local()
        return super().get_queryset().filter(tenant=_thread_locals.current_tenant)
```

### Risks
- Missing a single queryset = data leak between tenants
- Every new feature must remember to scope by tenant
- No enforcement at the database level

### Effort estimate
| Task | Time |
|---|---|
| Tenant model + 14 model migrations | 1 day |
| Middleware + auth wiring | 4 hours |
| Update ~150 querysets in views | 2–3 days |
| Update all form saves | 1 day |
| Fix Settings.objects.first() (30 places) | 4 hours |
| Testing + catching missed querysets | 1–2 days |
| **Total** | **~4–6 days** |

---

## Decision

| | Option A (django-tenants) | Option B (row-level) |
|---|---|---|
| Data isolation | Database-level (safe) | Application-level (risky) |
| Model changes | None | 14 models |
| View changes | None | ~150 querysets |
| Requires Postgres for dev | Yes | No |
| Ongoing risk | Low | High (easy to miss a filter) |
| Effort | 2–3 days | 4–6 days |
| **Verdict** | ✅ Recommended | ⚠️ Not recommended |

**Go with Option A.**
