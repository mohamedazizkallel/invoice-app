from django.shortcuts import redirect


def _settings_complete():
    """Returns True if the current tenant's Settings has all required fields."""
    from sales.models import Settings
    s = Settings.get_cached()
    return bool(s and s.clientname and s.mf and s.adress and s.emailAddress)


class SetupRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            path = request.path
            exempt = path == '/' or any(
                path.startswith(p) for p in ('/setup/', '/logout', '/admin/', '/api/')
            )
            if not exempt and not _settings_complete():
                return redirect('setup_wizard')
        return self.get_response(request)


def settings_context(request):
    """Injects settings_complete into every template context."""
    if not request.user.is_authenticated:
        return {}
    return {'settings_complete': _settings_complete()}
