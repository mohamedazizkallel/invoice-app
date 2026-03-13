from django.db import models
from sales.models import Invoice

class GovInvoice(models.Model):
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE)

    unsigned_xml = models.BinaryField()
    signature_xml = models.BinaryField(null=True)
    signed_xml = models.BinaryField(null=True)

    status = models.CharField(
        choices=[
            ("draft", "Draft"),
            ("signed", "Signed"),
            ("sent", "Sent"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ]
    )

    ngsign_transaction_uuid = models.CharField(max_length=100, null=True, blank=True)
    ngsign_invoice_uuid = models.CharField(max_length=100, null=True, blank=True)
    ngsign_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('CREATED', 'CREATED'),
            ('CONFIGURED', 'CONFIGURED'),
            ('SIGNED', 'SIGNED'),
            ('CANCELLED', 'CANCELLED'),
            ('TTN_TRANSFERED', 'TTN_TRANSFERED'),
            ('TTN_NOTTRANSFERED', 'TTN_NOTTRANSFERED'),
            ('TTN_REJECTED', 'TTN_REJECTED'),
            ('TTN_SIGNED', 'TTN_SIGNED'),
            ('MIXED', 'MIXED'),
            ('ERROR', 'ERROR'),
        ]
    )

    created_at = models.DateTimeField(auto_now_add=True)
