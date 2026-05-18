import pytest
from django.db import connection
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestElfatooraSettingsView:
    @pytest.fixture(autouse=True)
    def _clean_account(self, tenant):
        from tenants.models import ElfatooraClientAccount
        current = connection.schema_name
        connection.set_schema_to_public()
        ElfatooraClientAccount.objects.filter(tenant=tenant).delete()
        connection.set_schema(current)
        yield
        connection.set_schema_to_public()
        ElfatooraClientAccount.objects.filter(tenant=tenant).delete()
        connection.set_schema(current)

    def _get_account(self, tenant):
        from tenants.models import ElfatooraClientAccount
        current = connection.schema_name
        connection.set_schema_to_public()
        try:
            return ElfatooraClientAccount.objects.filter(tenant=tenant).first()
        finally:
            connection.set_schema(current)

    def test_get_empty(self, logged_in_client, tenant, seller):
        resp = logged_in_client.get(reverse('elfatoora_settings'))
        assert resp.status_code == 200
        assert b'Aucun compte elfatoora' in resp.content

    def test_post_creates_account(self, logged_in_client, tenant, seller):
        resp = logged_in_client.post(reverse('elfatoora_settings'), data={
            'username': 'newuser',
            'password': 'secret123',
            'mf': '0000000ABC',
        })
        assert resp.status_code == 302

        account = self._get_account(tenant)
        assert account is not None
        assert account.username == 'NEWUSER'  # uppercased by clean_username
        assert account.password == 'secret123'
        assert account.mf == '0000000ABC'
        assert account.status == 'PENDING'

    def test_post_requires_password_when_creating(self, logged_in_client, tenant, seller):
        resp = logged_in_client.post(reverse('elfatoora_settings'), data={
            'username': 'u',
            'password': '',
            'mf': 'MF',
        })
        assert resp.status_code == 200
        assert self._get_account(tenant) is None

    def test_post_updates_without_password(self, logged_in_client, tenant, seller, elfatoora_account):
        old_password = elfatoora_account.password

        resp = logged_in_client.post(reverse('elfatoora_settings'), data={
            'username': 'newname',
            'password': '',
            'mf': '999AAA',
        })
        assert resp.status_code == 302

        account = self._get_account(tenant)
        assert account.username == 'NEWNAME'
        assert account.mf == '999AAA'
        assert account.password == old_password  # preserved

    def test_post_updates_password_when_provided(self, logged_in_client, tenant, seller, elfatoora_account):
        resp = logged_in_client.post(reverse('elfatoora_settings'), data={
            'username': elfatoora_account.username,
            'password': 'brandnew',
            'mf': elfatoora_account.mf,
        })
        assert resp.status_code == 302

        account = self._get_account(tenant)
        assert account.password == 'brandnew'

    def test_get_prefills_username_and_mf_but_not_password(
        self, logged_in_client, tenant, seller, elfatoora_account
    ):
        resp = logged_in_client.get(reverse('elfatoora_settings'))
        assert resp.status_code == 200
        assert elfatoora_account.username.encode() in resp.content
        assert elfatoora_account.mf.encode() in resp.content
        assert elfatoora_account.password.encode() not in resp.content

    def test_requires_login(self, client, tenant):
        resp = client.get(reverse('elfatoora_settings'))
        assert resp.status_code in (302, 401, 403)
