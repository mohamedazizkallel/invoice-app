from django.contrib import admin
from .models import (
    Client, Invoice, Settings, Service, InvoiceService,
    ClientTransaction, Purchase, PurchaseLine, InvoiceSupplyUsage,
    Supplier, Supply, CreditNote, BonLivraison, Devis,
)

admin.site.register(Client)
admin.site.register(Settings)
admin.site.register(Invoice)
admin.site.register(ClientTransaction)
admin.site.register(Purchase)
admin.site.register(PurchaseLine)
admin.site.register(InvoiceSupplyUsage)
admin.site.register(InvoiceService)
admin.site.register(Service)
admin.site.register(Supplier)
admin.site.register(Supply)
admin.site.register(CreditNote)
admin.site.register(BonLivraison)
admin.site.register(Devis)
