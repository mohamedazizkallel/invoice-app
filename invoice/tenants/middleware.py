from django.db import connection
from django.http import HttpResponseForbidden
from django_tenants.utils import get_public_schema_name

from tenants.models import Tenant


class SessionTenantMiddleware:
    """
    Sets the tenant schema based on the logged-in user's TenantUser record.
    Unauthenticated requests (login page, etc.) use the public schema.
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
        else:
            # Superuser schema override: lets an admin point the active schema at
            # any tenant via /switch-schema/ to browse/edit tenant data in admin.
            admin_schema = request.session.get('admin_schema') if request.user.is_superuser else None
            if admin_schema:
                connection.set_schema_to_public()
                t = Tenant.objects.filter(schema_name=admin_schema).first()
                if t:
                    connection.set_tenant(t)
                else:
                    connection.set_schema_to_public()
                    request.session.pop('admin_schema', None)
            else:
                try:
                    tenant = request.user.tenant_user.tenant
                    connection.set_tenant(tenant)
                except Exception:
                    if request.user.is_superuser:
                        connection.set_schema_to_public()
                    else:
                        return HttpResponseForbidden("No tenant assigned to this user.")

        return self.get_response(request)
