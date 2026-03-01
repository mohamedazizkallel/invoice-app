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
            # Not logged in — stay on public schema (login page, static files, etc.)
            tenant = Tenant.objects.filter(
                schema_name=get_public_schema_name()
            ).first()
            if tenant:
                connection.set_tenant(tenant)
        else:
            try:
                tenant = request.user.tenant_user.tenant
                connection.set_tenant(tenant)
            except Exception:
                return HttpResponseForbidden("No tenant assigned to this user.")

        return self.get_response(request)
