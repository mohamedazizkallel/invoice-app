from django.urls import path
from .views import (dashboard, delete_supplier, edit_supplier,
                    login_view,add_service,
                    logout_view,settings_view,edit_client,service_view,edit_service,delete_service,
                    invoice_delete
                    ,invoices_list,invoice_create,invoice_detail,invoice_edit,invoice_modal_data,
                    clients, mf_map,
                    delete_client, suppliers,
                    client_transactions, client_add_transaction, client_delete_transaction, client_unpaid_invoices,
                    supplier_transactions, supplier_add_transaction,
                    supplies_list, supply_create, supply_edit, supply_delete,
                    purchases_list, purchase_create, purchase_detail, purchase_edit,
                    purchase_delete, purchase_confirm, process_purchase_payment,
                    purchase_retenu_create, purchase_retenu_delete,
                    purchase_download_xml, purchase_detail_modal,
                    company_logo,
                    avoirs_list, avoir_create, avoir_edit, avoir_delete,
                    avoir_detail, avoir_modal_data, client_all_invoices,
                    bons_livraison_list, bon_livraison_create, bon_livraison_edit,
                    bon_livraison_delete, bon_livraison_detail, bon_livraison_modal_data,
                    devis_list, devis_create, devis_detail, devis_update, devis_delete, devis_convert,
                    invoice_ngsign_submit, invoice_ngsign_check,
                    avoir_ngsign_submit, avoir_ngsign_check,
                    ngsign_pending_api)

urlpatterns = [
    path('', login_view,name='login'),
    path('logout', logout_view,name='logout'),
    path('dashboard/', dashboard,name='dashboard'),
    path('logo/', company_logo, name='company_logo'),
    path('settings/', settings_view,name='settings_view'),
    path('clients/', clients,name='clients'),
    path('clients/<int:client_id>/edit/', edit_client,name='edit_client'),
    path('clients/<int:client_id>/transactions/', client_transactions, name='client_transactions'),
    path('clients/<int:client_id>/transactions/add/', client_add_transaction, name='client_add_transaction'),
    path('transactions/<int:transaction_id>/delete/', client_delete_transaction, name='client_delete_transaction'),
    path('clients/<int:client_id>/unpaid-invoices/', client_unpaid_invoices, name='client_unpaid_invoices'),
    path('client/<int:pk>/delete/',delete_client, name='delete-client'),
    path('mf-map/', mf_map, name='mf_map'),
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
    path('invoices/<int:invoice_id>/ngsign/submit/', invoice_ngsign_submit, name='invoice-ngsign-submit'),
    path('invoices/<int:invoice_id>/ngsign/check/', invoice_ngsign_check, name='invoice-ngsign-check'),

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

    # Avoirs (Factures d'Avoir / Credit Notes)
    path('avoirs/', avoirs_list, name='avoirs_list'),
    path('avoirs/create/', avoir_create, name='avoir_create'),
    path('avoirs/<int:avoir_id>/', avoir_detail, name='avoir_detail'),
    path('avoirs/<int:avoir_id>/edit/', avoir_edit, name='avoir_edit'),
    path('avoirs/<int:avoir_id>/delete/', avoir_delete, name='avoir_delete'),
    path('avoirs/<int:avoir_id>/modal-data/', avoir_modal_data, name='avoir_modal_data'),
    path('avoirs/<int:avoir_id>/ngsign/submit/', avoir_ngsign_submit, name='avoir-ngsign-submit'),
    path('avoirs/<int:avoir_id>/ngsign/check/', avoir_ngsign_check, name='avoir-ngsign-check'),

    # NGSign API
    path('api/ngsign/pending/', ngsign_pending_api, name='ngsign-pending-api'),
    path('clients/<int:client_id>/all-invoices/', client_all_invoices, name='client_all_invoices'),

    # Bons de Livraison
    path('bons-livraison/', bons_livraison_list, name='bons_livraison_list'),
    path('bons-livraison/create/', bon_livraison_create, name='bon_livraison_create'),
    path('bons-livraison/<int:bon_id>/', bon_livraison_detail, name='bon_livraison_detail'),
    path('bons-livraison/<int:bon_id>/edit/', bon_livraison_edit, name='bon_livraison_edit'),
    path('bons-livraison/<int:bon_id>/delete/', bon_livraison_delete, name='bon_livraison_delete'),
    path('bons-livraison/<int:bon_id>/modal-data/', bon_livraison_modal_data, name='bon_livraison_modal_data'),

    # Devis (Quotes)
    path('devis/', devis_list, name='devis_list'),
    path('devis/create/', devis_create, name='devis_create'),
    path('devis/<int:devis_id>/', devis_detail, name='devis_detail'),
    path('devis/<int:devis_id>/update/', devis_update, name='devis_update'),
    path('devis/<int:devis_id>/delete/', devis_delete, name='devis_delete'),
    path('devis/<int:devis_id>/convert/', devis_convert, name='devis_convert'),
]
