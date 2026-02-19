from django.urls import path
from .views import (dashboard, delete_supplier, edit_supplier,
                    login_view,add_service,
                    logout_view,settings_view,edit_client,service_view,edit_service,delete_service,
                    invoice_delete,export_invoices,import_invoices,download_invoice_template
                    ,invoices_list,invoice_create,invoice_detail,invoice_edit,invoice_modal_data,
                    clients,
                    delete_client, suppliers,
                    client_transactions, client_add_transaction,
                    supplier_transactions, supplier_add_transaction,
                    supplies_list, supply_create, supply_edit, supply_delete,
                    purchases_list, purchase_create, purchase_detail, purchase_edit,
                    purchase_delete, purchase_confirm, process_purchase_payment,
                    purchase_retenu_create, purchase_retenu_delete,
                    purchase_download_xml, purchase_detail_modal)

urlpatterns = [
    path('', login_view,name='login'),
    path('logout', logout_view,name='logout'),
    path('dashboard/', dashboard,name='dashboard'),
    path('settings/', settings_view,name='settings_view'),
    path('clients/', clients,name='clients'),
    path('clients/<int:client_id>/edit/', edit_client,name='edit_client'),
    path('clients/<int:client_id>/transactions/', client_transactions, name='client_transactions'),
    path('clients/<int:client_id>/transactions/add/', client_add_transaction, name='client_add_transaction'),
    path('client/<int:pk>/delete/',delete_client, name='delete-client'),
    path('suppliers/', suppliers,name='suppliers'),
    path('suppliers/<int:client_id>/edit/', edit_supplier,name='edit_supplier'),
    path('suppliers/<int:pk>/delete/',delete_supplier, name='delete-supplier'),
    path('suppliers/<int:supplier_id>/transactions/', supplier_transactions, name='supplier_transactions'),
    path('suppliers/<int:supplier_id>/transactions/add/', supplier_add_transaction, name='supplier_add_transaction'),

    # Invoices
    path('invoices/', invoices_list, name='invoices_list'),
    path('invoices/create/', invoice_create, name='invoice_create'),
    path('invoices/<int:invoice_id>/', invoice_detail, name='invoice_detail'),
    path('invoices/<slug:slug>/', invoice_detail, name='invoice-detail-service'),
    path('invoices/<int:invoice_id>/edit/', invoice_edit, name='invoice_edit'),
    path('invoices/<int:invoice_id>/modal-data/', invoice_modal_data, name='invoice_modal_data'),
    path('invoices/<int:invoice_id>/delete/', invoice_delete, name='invoice_delete'),
    path('invoices/export/', export_invoices, name='export_invoices'),
    path('invoices/import/', import_invoices, name='import_invoices'),
    path('invoices/template/', download_invoice_template, name='download_invoice_template'),

    # Services
    path('Services/', service_view, name='services_list'),
    path('Services/add/', add_service, name='add_service'),
    path('Services/<int:service_id>/edit/', edit_service, name='edit_service'),
    path('Services/<int:service_id>/delete/', delete_service, name='delete_service'),

    # Supplies
    path('supplies/', supplies_list, name='supplies_list'),
    path('supplies/create/', supply_create, name='supply_create'),
    path('supplies/<int:supply_id>/edit/', supply_edit, name='supply_edit'),
    path('supplies/<int:supply_id>/delete/', supply_delete, name='supply_delete'),

    # Purchases
    path('purchases/', purchases_list, name='purchases_list'),
    path('purchases/create/', purchase_create, name='purchase_create'),
    path('purchases/<int:purchase_id>/', purchase_detail, name='purchase_detail'),
    path('purchases/<int:purchase_id>/edit/', purchase_edit, name='purchase_edit'),
    path('purchases/<int:purchase_id>/delete/', purchase_delete, name='purchase_delete'),
    path('purchases/<int:purchase_id>/confirm/', purchase_confirm, name='purchase_confirm'),
    path('purchases/<int:purchase_id>/payment/', process_purchase_payment, name='process_purchase_payment'),
    path('purchases/<int:purchase_id>/retenu/create/', purchase_retenu_create, name='purchase_retenu_create'),
    path('purchases/retenu/<int:retenu_id>/delete/', purchase_retenu_delete, name='purchase_retenu_delete'),
    path('purchases/<int:purchase_id>/download-xml/', purchase_download_xml, name='purchase_download_xml'),
    path('purchases/<int:purchase_id>/modal/', purchase_detail_modal, name='purchase_detail_modal'),
]
