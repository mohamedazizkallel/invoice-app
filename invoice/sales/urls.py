from django.contrib import admin
from django.urls import path
from .views import (index,
                    dashboard,
                    login_view,
                    logout_view,companysettings,delete_settings,
                    invoice_delete,export_invoices,import_invoices,download_invoice_template
                    ,invoices_list,invoice_create,invoice_detail,invoice_edit,
                    clients,export_products,import_products,download_product_template,
                    delete_client,products_list,add_product,edit_product,delete_product)

urlpatterns = [
    path('', index,name='index'),
    path('login', login_view,name='login'),
    path('login', logout_view,name='logout'),
    path('dashboard', dashboard,name='dashboard'),
    path('settings', companysettings,name='settings'),
    path('clients', clients,name='clients'),
    path('client/<int:pk>/delete/',delete_client, name='delete-client'),
    path('settings/<int:pk>/delete/',delete_settings, name='delete-settings'),
    path('products/', products_list, name='products_list'),
    path('products/add/', add_product, name='add_product'),
    path('products/<int:product_id>/edit/', edit_product, name='edit_product'),
    path('products/<int:product_id>/delete/', delete_product, name='delete_product'),
    path('products/export/', export_products, name='export_products'),
    path('products/import/', import_products, name='import_products'),
    path('products/template/', download_product_template, name='download_product_template'),
        # Invoices
    path('invoices/', invoices_list, name='invoices_list'),
    path('invoices/create/', invoice_create, name='invoice_create'),
    path('invoices/<int:invoice_id>/', invoice_detail, name='invoice_detail'),
    path('invoices/<int:invoice_id>/edit/', invoice_edit, name='invoice_edit'),
    path('invoices/<int:invoice_id>/delete/', invoice_delete, name='invoice_delete'),
    path('invoices/export/', export_invoices, name='export_invoices'),
    path('invoices/import/', import_invoices, name='import_invoices'),
    path('invoices/template/', download_invoice_template, name='download_invoice_template'),
]
