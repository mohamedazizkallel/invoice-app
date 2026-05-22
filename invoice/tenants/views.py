from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection
from django.shortcuts import redirect, render

from tenants.models import Tenant


def _is_superuser(u):
    return u.is_authenticated and u.is_superuser


@login_required
@user_passes_test(_is_superuser)
def switch_schema(request):
    """Superuser-only: point the admin's active schema at a tenant (or public).

    Stored in session['admin_schema']; SessionTenantMiddleware applies it on
    each request so /admin/ operates on the chosen tenant's data.
    """
    connection.set_schema_to_public()
    tenants = list(Tenant.objects.exclude(schema_name='public').order_by('schema_name'))

    if request.method == 'POST':
        schema = (request.POST.get('schema') or '').strip()
        if not schema or schema == 'public':
            request.session.pop('admin_schema', None)
            messages.success(request, 'Schéma actif : public.')
        elif Tenant.objects.filter(schema_name=schema).exists():
            request.session['admin_schema'] = schema
            messages.success(request, f'Schéma actif : {schema}. L’admin édite désormais ce client.')
        else:
            messages.error(request, f'Schéma introuvable : {schema}')
        # Return to wherever the switch was triggered (e.g. the admin page).
        nxt = request.POST.get('next') or ''
        if nxt.startswith('/'):
            return redirect(nxt)
        return redirect('switch_schema')

    current = request.session.get('admin_schema', 'public')
    return render(request, 'tenants/switch_schema.html', {
        'tenants': tenants,
        'current': current,
    })
