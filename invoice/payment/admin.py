from django.contrib import admin

from .models import Retenu, InvoiceRetenu, PurchaseRetenu

# Tenant models — switch the admin to a tenant schema (/switch-schema/) first.
admin.site.register(Retenu)
admin.site.register(InvoiceRetenu)
admin.site.register(PurchaseRetenu)
