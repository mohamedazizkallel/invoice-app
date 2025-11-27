from django.contrib import admin
from django.urls import path
from .views import (index,
                    dashboard,
                    login_view,
                    logout_view,
                    invoices,
                    products,
                    clients)

urlpatterns = [
    path('', index,name='index'),
    path('login', login_view,name='login'),
    path('login', logout_view,name='logout'),
    path('dashboard', dashboard,name='dashboard'),
    path('invoice', invoices,name='invoices'),
    path('products', products,name='products'),
    path('clients', clients,name='clients'),
]
