import pytest
from django.db import connection
from django.test import Client
from django.urls import reverse


@pytest.fixture
def superuser(tenant):
    """Create a superuser in the public schema (no TenantUser)."""
    from django.contrib.auth.models import User
    current = connection.schema_name
    connection.set_schema_to_public()
    try:
        u, _ = User.objects.get_or_create(
            username='root', defaults={'is_active': True, 'is_staff': True, 'is_superuser': True}
        )
        u.is_staff = True
        u.is_superuser = True
        u.set_password('rootpass123')
        u.save()
    finally:
        connection.set_schema(current)
    return u


@pytest.fixture
def super_client(superuser):
    c = Client()
    c.login(username='root', password='rootpass123')
    return c


@pytest.mark.django_db(transaction=True)
class TestSwitchSchema:
    @pytest.fixture(autouse=True)
    def _restore_schema(self, tenant):
        # The view/middleware change connection schema per request; restore the
        # fixture's tenant schema so transaction=True teardown flushes cleanly.
        yield
        connection.set_schema('test_tenant')

    def test_get_renders_for_superuser(self, tenant, super_client):
        resp = super_client.get(reverse('switch_schema'))
        assert resp.status_code == 200
        assert b'public' in resp.content

    def test_post_sets_tenant_schema_in_session(self, tenant, super_client):
        resp = super_client.post(reverse('switch_schema'), data={'schema': 'test_tenant'})
        assert resp.status_code == 302
        assert super_client.session.get('admin_schema') == 'test_tenant'

    def test_post_public_clears_session(self, tenant, super_client):
        super_client.post(reverse('switch_schema'), data={'schema': 'test_tenant'})
        super_client.post(reverse('switch_schema'), data={'schema': 'public'})
        assert super_client.session.get('admin_schema') is None

    def test_post_unknown_schema_rejected(self, tenant, super_client):
        super_client.post(reverse('switch_schema'), data={'schema': 'nope_xyz'})
        assert super_client.session.get('admin_schema') is None

    def test_non_superuser_denied(self, tenant, logged_in_client):
        resp = logged_in_client.get(reverse('switch_schema'))
        # user_passes_test redirects to login (with ?next=) when check fails —
        # access denied (not a 200 render of the switch page).
        assert resp.status_code == 302
        assert resp.url.startswith('/?next=') or '/login' in resp.url

    def test_anonymous_denied(self, tenant):
        resp = Client().get(reverse('switch_schema'))
        assert resp.status_code == 302
