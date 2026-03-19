import pytest
from unittest.mock import patch
from django.db import connection


@pytest.fixture(scope='session')
def tenant_setup(django_db_setup, django_db_blocker):
    """Create a test tenant and switch to its schema. Runs once per test session."""
    with django_db_blocker.unblock():
        from tenants.models import Tenant, Domain
        tenant = Tenant(schema_name='test_tenant', name='Test Tenant')
        tenant.save()
        Domain.objects.create(domain='test.localhost', tenant=tenant, is_primary=True)
        connection.set_schema('test_tenant')
    yield tenant
    with django_db_blocker.unblock():
        connection.set_schema_to_public()
        tenant.delete(force_drop=True)


@pytest.fixture
def tenant(tenant_setup, db):
    """Per-test fixture that ensures tenant schema is active."""
    connection.set_schema('test_tenant')
    return tenant_setup


@pytest.fixture
def user(tenant):
    """Create a test user in the tenant schema."""
    from django.contrib.auth.models import User
    return User.objects.create_user(username='testuser', password='testpass123')


@pytest.fixture
def logged_in_client(user):
    """Return an authenticated Django test client."""
    from django.test import Client
    client = Client()
    client.login(username='testuser', password='testpass123')
    return client


@pytest.fixture
def seller(tenant):
    """Create a Settings (seller) instance.
    Mocks _sync_ngsign_org to prevent real NGSign API calls on Settings.save()."""
    from tests.factories import SettingsFactory
    with patch('sales.models._sync_ngsign_org'):
        return SettingsFactory()


@pytest.fixture
def ngsign_account(tenant_setup, db):
    """Create an NGSignClientAccount in the public schema for the test tenant."""
    current = connection.schema_name
    connection.set_schema_to_public()
    from tenants.models import NGSignClientAccount
    account, _ = NGSignClientAccount.objects.update_or_create(
        tenant=tenant_setup,
        defaults={
            'org_uuid': 'test-org-uuid',
            'org_jwt': 'test-org-jwt-token',
            'signer_email': 'signer@test.com',
            'status': 'ACTIVE',
        },
    )
    connection.set_schema(current)
    yield account
    connection.set_schema_to_public()
    account.delete()
    connection.set_schema(current)
