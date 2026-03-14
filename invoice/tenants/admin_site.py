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
            # Query tenants from public schema regardless of current schema
            from django_tenants.utils import get_public_schema_name
            connection.set_schema_to_public()
            ctx['available_tenants'] = (
                Tenant.objects
                .exclude(schema_name=get_public_schema_name())
                .order_by('name')
            )
            # Restore the schema from session if set
            schema = getattr(request, 'session', {}).get('_admin_schema')
            if schema:
                tenant = Tenant.objects.filter(schema_name=schema).first()
                if tenant:
                    connection.set_tenant(tenant)
            ctx['current_schema'] = connection.schema_name
        return ctx
