from django.contrib.admin import AdminSite
from django.db import connection
from django_tenants.utils import get_public_schema_name
from tenants.models import Tenant


class TenantAwareAdminSite(AdminSite):
    """Admin site that adds a tenant switcher for superusers."""

    index_template = 'tenant_admin/index.html'

    def each_context(self, request):
        ctx = super().each_context(request)
        if request.user.is_authenticated and request.user.is_superuser:
            # Tenants table is in public schema but we can query it
            # from any schema since it's a shared model — no need to switch.
            ctx['available_tenants'] = (
                Tenant.objects
                .exclude(schema_name=get_public_schema_name())
                .order_by('name')
            )
            ctx['current_schema'] = connection.schema_name
        return ctx
