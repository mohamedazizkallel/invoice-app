import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestDevisViews:
    def test_devis_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory, ServiceFactory
        from sales.models import Devis, InvoiceService
        client = ClientFactory()
        service = ServiceFactory()
        resp = logged_in_client.post(reverse('devis_create'), {
            'client': client.id,
            'title': 'Test Devis',
            'service_id[]': [service.id],
            'unit_price[]': ['100.000'],
            'has_fodec[]': ['0'],
            'hours_used[]': [''],
            'days_used[]': [''],
            'units_used[]': [''],
            'tva': '19',
            'timbre_fiscal': '1.000',
            'discount': '0',
        })
        assert resp.status_code == 302
        devis = Devis.objects.filter(client=client).first()
        assert devis is not None
        assert InvoiceService.objects.filter(devis=devis).exists()

    def test_devis_update_fields(self, tenant, seller, logged_in_client):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory(title='Original')
        DevisServiceFactory(devis=devis)
        logged_in_client.post(reverse('devis_update', args=[devis.id]), {
            'title': 'Updated Title',
            'notes': 'New notes',
            'discount': '5',
        })
        devis.refresh_from_db()
        assert devis.title == 'Updated Title'

    def test_devis_convert_creates_invoice(self, tenant, seller, logged_in_client):
        from tests.factories import DevisFactory, DevisServiceFactory
        devis = DevisFactory()
        DevisServiceFactory(devis=devis)
        resp = logged_in_client.post(reverse('devis_convert', args=[devis.id]))
        assert resp.status_code == 302
        devis.refresh_from_db()
        assert devis.status == 'ACCEPTED'
        assert devis.converted_invoice is not None

    def test_devis_convert_already_converted(self, tenant, seller, logged_in_client):
        from tests.factories import DevisFactory, DevisServiceFactory, InvoiceFactory
        invoice = InvoiceFactory()
        devis = DevisFactory(converted_invoice=invoice, status='ACCEPTED')
        resp = logged_in_client.post(reverse('devis_convert', args=[devis.id]))
        assert resp.status_code == 302

    def test_devis_delete(self, tenant, seller, logged_in_client):
        from tests.factories import DevisFactory
        from sales.models import Devis
        devis = DevisFactory()
        logged_in_client.post(reverse('devis_delete', args=[devis.id]))
        assert not Devis.objects.filter(pk=devis.pk).exists()
