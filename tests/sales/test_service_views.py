import pytest
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestServiceViews:
    def test_service_list_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('services_list'))
        assert resp.status_code == 200

    def test_service_list_search(self, tenant, seller, logged_in_client):
        from tests.factories import ServiceFactory
        ServiceFactory(title='UniqueServiceName')
        resp = logged_in_client.get(reverse('services_list'), {'search': 'UniqueServiceName'})
        assert resp.status_code == 200

    def test_add_service(self, tenant, seller, logged_in_client):
        from sales.models import Service
        resp = logged_in_client.post(reverse('add_service'), {
            'title': 'New Service',
            'billing_type': 'flat',
            'price': '100.000',
            'currency': 'TND',
            'service_type': 'service',
        })
        assert resp.status_code == 302
        assert Service.objects.filter(title='New Service').exists()

    def test_delete_service(self, tenant, seller, logged_in_client):
        from tests.factories import ServiceFactory
        from sales.models import Service
        svc = ServiceFactory()
        logged_in_client.post(reverse('delete_service', args=[svc.id]))
        assert not Service.objects.filter(pk=svc.pk).exists()
