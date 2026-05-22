import pytest
from unittest.mock import patch
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestSettingsViews:
    def test_settings_view_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('settings_view'))
        assert resp.status_code == 200

    def test_settings_save_updates_fields(self, tenant, seller, logged_in_client):
        with patch('sales.models._sync_ngsign_org'):
            resp = logged_in_client.post(reverse('settings_view'), {
                'clientname': 'Updated Company',
                'mf': seller.mf,
                'adress': 'New Address',
                'tva': '19.00',
                'dt': '1.000',
            })
        assert resp.status_code == 302
        seller.refresh_from_db()
        assert seller.clientname == 'Updated Company'

    def test_company_logo_serves_base64(self, tenant, logged_in_client):
        from sales.models import Settings
        from unittest.mock import patch
        with patch('sales.models._sync_ngsign_org'):
            s = Settings.objects.create(
                clientname='Logo Co',
                mf='1234567ABC000',
                adress='123 Rue Test, Tunis',
                emailAddress='logo@co.tn',
                clientLogo='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            )
        resp = logged_in_client.get(reverse('company_logo'))
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'image/png'
