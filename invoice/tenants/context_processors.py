def tenant_admin(request):
    """Expose the active admin schema + tenant list to admin templates.

    Only for superusers (the schema switcher is superuser-only). Tenant lives in
    the shared/public schema and stays on the search_path even when a tenant
    schema is active, so it's queryable without switching the connection.
    """
    u = getattr(request, 'user', None)
    if not (u and u.is_authenticated and u.is_superuser):
        return {}
    from tenants.models import Tenant
    try:
        tenants = list(Tenant.objects.exclude(schema_name='public').order_by('schema_name'))
    except Exception:
        tenants = []
    return {
        'tenant_admin_current': request.session.get('admin_schema', 'public'),
        'tenant_admin_list': tenants,
    }
