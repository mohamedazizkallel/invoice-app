import base64
from gov.pdf import render_invoice_pdf, render_avoir_pdf
from sales.models import Settings


def build_payload(gov_invoice):
    """
    Build the payload for /protected/invoice/xml/transaction/create.
    Handles both invoices and credit notes (avoirs).
    """
    seller = Settings.get_cached()

    if gov_invoice.credit_note:
        credit_note = gov_invoice.credit_note
        pdf_bytes = render_avoir_pdf(credit_note, seller)
        return {
            'invoiceFileB64': base64.b64encode(pdf_bytes).decode(),
            'invoiceTIEF': base64.b64encode(bytes(gov_invoice.unsigned_xml)).decode(),
            'invoiceNumber': credit_note.uniqueId,
            'clientEmail': getattr(credit_note.client, 'emailAddress', None) or '',
            'configuration': {
                'allPages': True,
                'qrPositionX': 0,
                'qrPositionY': 0,
                'qrPositionP': 0,
            },
        }

    invoice = gov_invoice.invoice
    pdf_bytes = render_invoice_pdf(invoice, seller)
    return {
        'invoiceFileB64': base64.b64encode(pdf_bytes).decode(),
        'invoiceTIEF': base64.b64encode(bytes(gov_invoice.unsigned_xml)).decode(),
        'invoiceNumber': invoice.uniqueId,
        'clientEmail': getattr(invoice.client, 'emailAddress', None) or '',
        'configuration': {
            'allPages': True,
            'qrPositionX': 0,
            'qrPositionY': 0,
            'qrPositionP': 0,
        },
    }
