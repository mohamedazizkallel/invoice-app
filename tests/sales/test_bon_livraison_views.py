import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestBonLivraisonViews:
    def test_bon_create_success(self, tenant, seller, logged_in_client):
        from tests.factories import ClientFactory
        from sales.models import BonLivraison
        client = ClientFactory()
        resp = logged_in_client.post(reverse('bon_livraison_create'), {
            'client': client.id,
            'tva': '19.000',
            'description[]': ['Item 1', 'Item 2'],
            'amount[]': ['100.000', '200.000'],
        })
        assert resp.status_code == 302
        assert BonLivraison.objects.filter(client=client).exists()

    def test_bon_detail_renders(self, tenant, seller, logged_in_client):
        from tests.factories import BonLivraisonFactory, BonLivraisonLineFactory
        bon = BonLivraisonFactory()
        BonLivraisonLineFactory(bon=bon)
        resp = logged_in_client.get(reverse('bon_livraison_detail', args=[bon.id]))
        assert resp.status_code == 200

    def test_bon_edit_rebuilds_lines(self, tenant, seller, logged_in_client):
        from tests.factories import BonLivraisonFactory, BonLivraisonLineFactory
        from sales.models import BonLivraisonLine
        bon = BonLivraisonFactory()
        BonLivraisonLineFactory(bon=bon)
        logged_in_client.post(reverse('bon_livraison_edit', args=[bon.id]), {
            'client': bon.client.id,
            'tva': '19.000',
            'description[]': ['New Item'],
            'amount[]': ['500.000'],
        })
        assert BonLivraisonLine.objects.filter(bon=bon).count() == 1
        assert BonLivraisonLine.objects.filter(bon=bon).first().amount == Decimal('500.000')

    def test_bon_delete(self, tenant, seller, logged_in_client):
        from tests.factories import BonLivraisonFactory
        from sales.models import BonLivraison
        bon = BonLivraisonFactory()
        logged_in_client.post(reverse('bon_livraison_delete', args=[bon.id]))
        assert not BonLivraison.objects.filter(pk=bon.pk).exists()
