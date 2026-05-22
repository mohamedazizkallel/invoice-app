"""Admin registration for tenant models.

These tables live in the *tenant* schemas, not public. To browse/edit them,
a superuser must first switch the admin's active schema via /switch-schema/
(see tenants.views.switch_schema). While the admin is in the public schema,
opening these changelists will error because the tables aren't there — that is
expected; switch to a tenant first.
"""
from django.contrib import admin

from .models import (
    Client, ClientTransaction, Supplier, SupplierTransaction, Supply,
    Purchase, PurchaseLine, Invoice, CreditNote, Settings, Service,
    BonLivraison, Devis, InvoiceService, NotificationState,
)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('uniqueId', 'client', 'status', 'date_created')
    search_fields = ('uniqueId',)
    list_filter = ('status',)


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ('uniqueId', 'client', 'date_created')
    search_fields = ('uniqueId',)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('clientname', 'mf', 'emailAddress')
    search_fields = ('clientname', 'mf')


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('clientname', 'mf', 'emailAddress')


# Remaining tenant models — default admin is enough for manual edits.
for _model in (
    ClientTransaction, Supplier, SupplierTransaction, Supply, Purchase,
    PurchaseLine, Service, BonLivraison, Devis, InvoiceService, NotificationState,
):
    admin.site.register(_model)
