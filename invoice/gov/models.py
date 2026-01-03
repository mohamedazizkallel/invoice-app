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

    created_at = models.DateTimeField(auto_now_add=True)
