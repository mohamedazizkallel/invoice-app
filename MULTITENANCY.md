# Multi-Tenancy Plan

## Current State
Single-tenant app. All users share the same data — no isolation between companies.
PostgreSQL in production, SQLite in dev.

---

## Approach — `django-tenants` (schema-per-tenant) + Session-Based Routing

Each tenant gets a dedicated PostgreSQL schema. Data is isolated at the database level.
No changes needed to existing models or view querysets.

**Routing:** Instead of subdomains (`company1.app.com`), the tenant is determined from
the logged-in user's session. Each `User` is linked to a `Tenant` via the `TenantUser`
model. No DNS configuration, wildcard SSL, or `/etc/hosts` hacking needed.

### How it works
1. A `Tenant` row is created for each company (creates a new PostgreSQL schema).
2. A `TenantUser` row links each `User` to their `Tenant`.
3. On every request, `SessionTenantMiddleware` reads `request.user` → looks up the tenant → calls `connection.set_tenant(tenant)`.
4. All queries (`Invoice.objects.all()`, etc.) automatically hit only that tenant's schema.
5. Unauthenticated requests (login page) use the `public` schema.

### Login flow
1. User hits `/login/` → public schema (no tenant context yet)
2. Django authenticates against `auth_user` in public schema
3. Session is created
4. Every subsequent request: middleware reads `request.user.tenant_user.tenant` → sets schema

---

### Implementation

**1. Install package**
```
pip install django-tenants
```

**2. `tenants` app — models**
```python
# tenants/models.py
from django.db import models
from django.contrib.auth.models import User
from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)
    auto_create_schema = True

class Domain(DomainMixin):
    """Required by django-tenants internally."""
    pass

class TenantUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant_user')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='users')
```

**3. Session-based middleware (replaces `TenantMainMiddleware`)**
```python
# tenants/middleware.py
from django.db import connection
from django.http import HttpResponseForbidden
from django_tenants.utils import get_public_schema_name
from tenants.models import Tenant

class SessionTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            tenant = Tenant.objects.filter(schema_name=get_public_schema_name()).first()
            if tenant:
                connection.set_tenant(tenant)
        else:
            try:
                tenant = request.user.tenant_user.tenant
                connection.set_tenant(tenant)
            except Exception:
                return HttpResponseForbidden("No tenant assigned to this user.")
        return self.get_response(request)
```

**4. settings.py changes**
```python
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
    'django.contrib.contenttypes',
    'sales',
    'payment',
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',  # required
        ...
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

TENANT_MODEL = 'tenants.Tenant'
TENANT_DOMAIN_MODEL = 'tenants.Domain'

MIDDLEWARE = [
    ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'tenants.middleware.SessionTenantMiddleware',  # after auth, NOT TenantMainMiddleware
    ...
]
```

**5. Migrate**
```bash
python manage.py migrate_schemas --shared   # sets up public schema + tenants tables
python manage.py migrate_schemas            # runs tenant migrations in each schema
```

**6. Create first tenant (via shell)**
```python
from tenants.models import Tenant, Domain, TenantUser
from django.contrib.auth.models import User

# Public tenant (required by django-tenants)
public = Tenant(schema_name='public', name='Public')
public.save()
Domain(domain='localhost', tenant=public, is_primary=True).save()

# First real tenant
tenant = Tenant(schema_name='company1', name='Company One')
tenant.save()

# Link existing user to tenant
user = User.objects.get(username='admin')
TenantUser.objects.create(user=user, tenant=tenant)
```

**7. Settings cache key — scoped per tenant**
```python
# Already updated in sales/models.py
@staticmethod
def _cache_key():
    from django.db import connection
    return f'company_settings_{connection.schema_name}'
```

**8. Dev environment**
SQLite does not support schemas. Run a local Postgres instance:
```bash
docker run -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=invoice -p 5432:5432 postgres
```

---

### What does NOT change
- All models (Client, Invoice, Supplier, Service, etc.) — untouched
- All 83+ URL patterns — untouched
- All views and querysets — untouched
- All templates — untouched
- Sequential IDs (FV-###-YEAR) — automatically isolated per schema

### Advantages over subdomain routing
- No wildcard DNS configuration needed
- No wildcard SSL certificate needed
- No `/etc/hosts` hacking for local development
- Single domain — works behind any reverse proxy as-is
- Simpler deployment (Dokploy, etc.)
