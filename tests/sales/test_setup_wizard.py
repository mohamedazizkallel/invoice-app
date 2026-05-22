import pytest
from unittest.mock import patch
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestSettingsComplete:
    def test_false_when_no_settings(self, tenant):
        from sales.middleware import _settings_complete
        assert _settings_complete() is False

    def test_false_when_email_missing(self, tenant):
        from sales.models import Settings
        from sales.middleware import _settings_complete
        with patch('sales.models._sync_ngsign_org'):
            Settings.objects.create(
                clientname='A', mf='123', adress='Tunis'
            )
        assert _settings_complete() is False

    def test_true_when_all_required_fields_set(self, tenant):
        from sales.models import Settings
        from sales.middleware import _settings_complete
        with patch('sales.models._sync_ngsign_org'):
            Settings.objects.create(
                clientname='A', mf='123', adress='Tunis',
                emailAddress='a@b.tn'
            )
        assert _settings_complete() is True


@pytest.mark.django_db(transaction=True)
class TestSetupRequiredMiddleware:
    def test_unauthenticated_not_redirected_to_setup(self, tenant):
        client = Client()
        resp = client.get('/dashboard/')
        assert resp.status_code == 302
        assert '/setup/' not in resp.url

    def test_incomplete_settings_redirects_to_setup(self, tenant, logged_in_client):
        resp = logged_in_client.get('/dashboard/')
        assert resp.status_code == 302
        assert resp.url == '/setup/'

    def test_setup_redirect_only_once_per_session(self, tenant, logged_in_client):
        # First hit while incomplete -> prompted to the wizard.
        first = logged_in_client.get('/dashboard/')
        assert first.status_code == 302 and first.url == '/setup/'
        # Subsequent hits must NOT force-redirect again (banner handles reminders).
        second = logged_in_client.get('/dashboard/')
        assert second.status_code == 200

    def test_complete_settings_passes_through(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get('/dashboard/')
        assert resp.status_code == 200

    def test_setup_url_is_exempt(self, tenant, logged_in_client):
        resp = logged_in_client.get('/setup/')
        assert resp.status_code in (200, 302)
        if resp.status_code == 302:
            assert resp.url != '/setup/'

    def test_api_url_is_exempt(self, tenant, logged_in_client):
        resp = logged_in_client.get('/api/ngsign/pending/')
        assert resp.status_code != 302 or '/setup/' not in (resp.url or '')

    def test_logout_url_is_exempt(self, tenant, logged_in_client):
        resp = logged_in_client.get('/logout')
        if resp.status_code == 302:
            assert '/setup/' not in resp.url


@pytest.mark.django_db(transaction=True)
class TestSettingsContextProcessor:
    def test_settings_complete_false_when_incomplete(self, tenant, logged_in_client):
        resp = logged_in_client.get('/setup/')
        assert resp.context['settings_complete'] is False

    def test_settings_complete_true_when_complete(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get('/setup/')
        assert resp.status_code == 302


@pytest.mark.django_db(transaction=True)
class TestSetupWizardView:
    def test_redirects_to_dashboard_when_already_complete(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get('/setup/')
        assert resp.status_code == 302
        assert resp.url == reverse('dashboard')

    def test_get_step1_renders(self, tenant, logged_in_client):
        resp = logged_in_client.get('/setup/')
        assert resp.status_code == 200
        assert resp.context['step'] == 1

    def test_post_step1_valid_advances_to_step2(self, tenant, logged_in_client):
        with patch('sales.models._sync_ngsign_org'):
            resp = logged_in_client.post('/setup/', {
                'action': 'next',
                'clientname': 'My Company',
                'emailAddress': 'contact@company.tn',
                'adress': '123 Rue Test, Tunis',
                'status': 'Person Physique',
                'phone': '',
            })
        assert resp.status_code == 302
        assert resp.url == '/setup/'
        resp2 = logged_in_client.get('/setup/')
        assert resp2.context['step'] == 2

    def test_post_step1_missing_required_rerenders(self, tenant, logged_in_client):
        resp = logged_in_client.post('/setup/', {
            'action': 'next',
            'clientname': '',
            'emailAddress': 'contact@company.tn',
            'adress': '123 Rue Test, Tunis',
        })
        assert resp.status_code == 200
        assert resp.context['step'] == 1

    def test_post_step2_valid_advances_to_step3(self, tenant, logged_in_client):
        from sales.models import Settings
        session = logged_in_client.session
        session['setup_step'] = 2
        session.save()
        with patch('sales.models._sync_ngsign_org'):
            Settings.objects.create(
                clientname='A', emailAddress='a@b.tn', adress='Tunis'
            )
            resp = logged_in_client.post('/setup/', {
                'action': 'next',
                'mf': '1234567ABC000',
                'tva': '19.00',
                'dt': '1.000',
                'default_retenu_rate': '',
            })
        assert resp.status_code == 302
        resp2 = logged_in_client.get('/setup/')
        assert resp2.context['step'] == 3

    def test_post_step3_skip_redirects_to_dashboard(self, tenant, logged_in_client):
        session = logged_in_client.session
        session['setup_step'] = 3
        session.save()
        resp = logged_in_client.post('/setup/', {'action': 'skip'})
        assert resp.status_code == 302
        assert resp.url == reverse('dashboard')
