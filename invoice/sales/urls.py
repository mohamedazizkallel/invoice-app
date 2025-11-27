from django.contrib import admin
from django.urls import path
from .views import (index,
                    dashboard,
                    login_view,
                    logout_view,
                    invoices,
                    products,
                    clients,export_products,import_products,download_product_template,
                    delete_client,products_list,add_product,edit_product,delete_product)

urlpatterns = [
    path('', index,name='index'),
    path('login', login_view,name='login'),
    path('login', logout_view,name='logout'),
    path('dashboard', dashboard,name='dashboard'),
    path('invoice', invoices,name='invoices'),
    path('products', products,name='products'),
    path('clients', clients,name='clients'),
    path('client/<int:pk>/delete/',delete_client, name='delete-client'),
    path('products/', products_list, name='products_list'),
    path('products/add/', add_product, name='add_product'),
    path('products/<int:product_id>/edit/', edit_product, name='edit_product'),
    path('products/<int:product_id>/delete/', delete_product, name='delete_product'),
    path('products/export/', export_products, name='export_products'),
    path('products/import/', import_products, name='import_products'),
    path('products/template/', download_product_template, name='download_product_template'),
]
