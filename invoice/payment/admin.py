from django.contrib import admin
from .models import Retenu, InvoiceRetenu, PurchaseRetenu

admin.site.register(Retenu)
admin.site.register(InvoiceRetenu)
admin.site.register(PurchaseRetenu)
