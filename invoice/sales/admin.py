from django.contrib import admin
from .models import Client, InvoiceService, InvoiceSupplyUsage, Purchase, PurchaseLine,Settings,Invoice,ClientTransaction

# Register your models here.
admin.site.register(Client)
admin.site.register(Settings)
admin.site.register(Invoice)
admin.site.register(ClientTransaction)
admin.site.register(Purchase)
admin.site.register(PurchaseLine)
admin.site.register(InvoiceSupplyUsage)
admin.site.register(InvoiceService)
