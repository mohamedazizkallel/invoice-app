from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from tenants.models import Tenant


@staff_member_required
def switch_tenant(request):
    """Let a superuser pick which tenant schema the admin should use."""
    schema = request.GET.get('schema')
    if request.user.is_superuser and schema:
        if Tenant.objects.filter(schema_name=schema).exists():
            request.session['_admin_schema'] = schema
    return redirect('admin:index')
