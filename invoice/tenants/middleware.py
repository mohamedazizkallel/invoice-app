from django.db import connection
from django.http import HttpResponseForbidden
from django_tenants.utils import get_public_schema_name

from tenants.models import Tenant


class SessionTenantMiddleware:
    """
    Sets the tenant schema based on the logged-in user's TenantUser record.

    Superusers can override the schema via session key '_admin_schema'
    (set by the tenant-switcher view) to browse any tenant's data in the admin.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            tenant = Tenant.objects.filter(
                schema_name=get_public_schema_name()
            ).first()
            if tenant:
                connection.set_tenant(tenant)
        elif request.user.is_superuser and '_admin_schema' in request.session:
            # Superuser with a schema override — use the selected tenant
            schema = request.session['_admin_schema']
            tenant = Tenant.objects.filter(schema_name=schema).first()
            if tenant:
                connection.set_tenant(tenant)
            else:
                # Invalid schema in session — fall back to public
                del request.session['_admin_schema']
                connection.set_schema_to_public()
        else:
            try:
                tenant = request.user.tenant_user.tenant
                connection.set_tenant(tenant)
            except Exception:
                if request.user.is_superuser:
                    # Superuser without a TenantUser — use public schema
                    connection.set_schema_to_public()
                else:
                    return HttpResponseForbidden("No tenant assigned to this user.")

        return self.get_response(request)
