from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from django_tenants.utils import get_public_schema_name
from tenants.models import Tenant


@staff_member_required
def switch_tenant(request):
    """Let a superuser pick which tenant schema the admin should use."""
    schema = request.GET.get('schema')
    if not request.user.is_superuser or not schema:
        return redirect('admin:index')

    if schema == get_public_schema_name():
        # Clear override — fall back to public schema
        request.session.pop('_admin_schema', None)
    elif Tenant.objects.filter(schema_name=schema).exists():
        request.session['_admin_schema'] = schema

    return redirect('admin:index')
