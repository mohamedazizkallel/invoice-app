import pytest
from decimal import Decimal
from django.urls import reverse


@pytest.mark.django_db(transaction=True)
class TestSupplierViews:
    def test_suppliers_list_renders(self, tenant, seller, logged_in_client):
        resp = logged_in_client.get(reverse('suppliers'))
        assert resp.status_code == 200

    def test_edit_supplier_updates_fields(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory
        supplier = SupplierFactory()
        logged_in_client.post(reverse('edit_supplier', args=[supplier.id]), {
            'name': 'Updated Supplier',
            'emailAddress': 'supplier@test.com',
            'adress': 'New Supplier St',
            'mf': 'NEWMF456',
        })
        supplier.refresh_from_db()
        assert supplier.name == 'Updated Supplier'

    def test_delete_supplier(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory
        from sales.models import Supplier
        supplier = SupplierFactory()
        logged_in_client.get(reverse('delete-supplier', args=[supplier.pk]))
        assert not Supplier.objects.filter(pk=supplier.pk).exists()

    def test_supplier_add_transaction(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory
        from sales.models import SupplierTransaction
        supplier = SupplierFactory()
        logged_in_client.post(reverse('supplier_add_transaction', args=[supplier.id]), {
            'transaction_type': 'CREDIT',
            'amount': '300.000',
            'description': 'Manual credit',
        })
        txn = SupplierTransaction.objects.filter(supplier=supplier).first()
        assert txn is not None
        assert txn.source == 'MANUAL'

    def test_supplier_transactions_json(self, tenant, seller, logged_in_client):
        from tests.factories import SupplierFactory, SupplierTransactionFactory
        supplier = SupplierFactory()
        SupplierTransactionFactory(supplier=supplier)
        resp = logged_in_client.get(reverse('supplier_transactions', args=[supplier.id]))
        assert resp.status_code == 200
