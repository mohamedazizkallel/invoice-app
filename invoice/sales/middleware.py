from django.shortcuts import redirect


def _settings_complete():
    """Returns True if the current tenant's Settings has all required fields.

    Resilient to running in the public schema (e.g. a superuser using the schema
    switcher), where the tenant-only `sales_settings` table doesn't exist —
    return False instead of letting the query crash the page.
    """
    from sales.models import Settings
    try:
        s = Settings.get_cached()
    except Exception:
        return False
    return bool(s and s.clientname and s.mf and s.adress and s.emailAddress)


class SetupRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            path = request.path
            exempt = path == '/' or any(
                path.startswith(p) for p in ('/setup/', '/logout', '/admin/', '/api/', '/switch-schema/')
            )
            # Redirect to the wizard only once per session. After the user has
            # been prompted (or skipped), the dismissible banner in base.html is
            # the ongoing reminder — don't force-redirect on every page.
            if not exempt and not _settings_complete() and not request.session.get('setup_prompted'):
                request.session['setup_prompted'] = True
                return redirect('setup_wizard')
        return self.get_response(request)


def settings_context(request):
    """Injects settings_complete into every template context."""
    if not request.user.is_authenticated:
        return {}
    return {'settings_complete': _settings_complete()}
