from django.contrib import admin

from .models import GovInvoice


@admin.register(GovInvoice)
class GovInvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice', 'credit_note', 'status', 'ngsign_status', 'elfatoora_status')
    list_filter = ('status', 'ngsign_status', 'elfatoora_status')
