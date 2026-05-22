from django.db import models
from sales.models import Invoice, CreditNote

class GovInvoice(models.Model):
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, null=True, blank=True)
    credit_note = models.OneToOneField(CreditNote, on_delete=models.CASCADE, null=True, blank=True)

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
            ('SUBMITTING', 'SUBMITTING'),
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

    elfatoora_generated_ref = models.CharField(max_length=100, null=True, blank=True)
    elfatoora_status = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        choices=[
            ('SUBMITTED', 'SUBMITTED'),
            ('ACKNOWLEDGED', 'ACKNOWLEDGED'),
            ('REJECTED', 'REJECTED'),
            ('ERROR', 'ERROR'),
        ],
    )
    elfatoora_submitted_at = models.DateTimeField(null=True, blank=True)
    elfatoora_last_ack_at = models.DateTimeField(null=True, blank=True)
    elfatoora_last_error = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default='')
    submitted_at = models.DateTimeField(null=True, blank=True)
