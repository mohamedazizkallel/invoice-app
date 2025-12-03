from django.contrib import admin
from django.urls import path
from .views import (index,
                    dashboard,
                    login_view,add_service,
                    logout_view,settings_view,edit_client,service_view,edit_service,delete_service,
                    invoice_delete,export_invoices,import_invoices,download_invoice_template
                    ,invoices_list,invoice_create,invoice_detail,invoice_edit,
                    clients,
                    delete_client)

urlpatterns = [
    path('', index,name='index'),
    path('login', login_view,name='login'),
    path('login', logout_view,name='logout'),
    path('dashboard', dashboard,name='dashboard'),
    path('settings', settings_view,name='settings_view'),
    path('clients', clients,name='clients'),
    path('clients/<int:client_id>/edit/', edit_client,name='edit_client'),
    path('client/<int:pk>/delete/',delete_client, name='delete-client'),
        # Invoices
    path('invoices/', invoices_list, name='invoices_list'),
    path('invoices/create/', invoice_create, name='invoice_create'),
    path('invoices/<int:invoice_id>/', invoice_detail, name='invoice_detail'),
    path('invoices/<int:invoice_id>/edit/', invoice_edit, name='invoice_edit'),
    path('invoices/<int:invoice_id>/delete/', invoice_delete, name='invoice_delete'),
    path('invoices/export/', export_invoices, name='export_invoices'),
    path('invoices/import/', import_invoices, name='import_invoices'),
    path('invoices/template/', download_invoice_template, name='download_invoice_template'),
        #services
    path('Services/', service_view, name='services_list'),
    path('Services/add/', add_service, name='add_service'),
    path('Services/<int:service_id>/edit/', edit_service, name='edit_service'),
    path('Services/<int:service_id>/delete/', delete_service, name='delete_service'),
]
