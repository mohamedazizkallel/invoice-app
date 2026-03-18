import io
from decimal import Decimal
from django.template.loader import render_to_string
from weasyprint import HTML


def render_invoice_pdf(invoice, seller):
    """Render an invoice to PDF bytes using WeasyPrint."""
    from sales.utilities import num2words_tnd_fr

    invoice_services = invoice.invoice_services.all()
    services_with_totals = []
    invoice_currency = 'TND'

    for inv_svc in invoice_services:
        service = inv_svc.service
        if invoice_currency == 'TND':
            invoice_currency = service.currency or 'TND'

        services_with_totals.append({
            'service': service,
            'unit_price': inv_svc.unit_price,
            'line_total': inv_svc.get_line_ht(),
            'has_fodec': inv_svc.has_fodec,
            'fodec_amount': inv_svc.get_fodec_amount(),
        })

    subtotal = invoice.calculate_service_subtotal()
    discount_amount = invoice.calculate_discount_amount() if invoice.discount else 0
    subtotal_after_discount = invoice.calculate_subtotal_after_discount()
    total_fodec = invoice.calculate_total_fodec()
    tva_amount = invoice.calculate_tva_amount()
    total = invoice.calculate_total()
    total_in_words = num2words_tnd_fr(Decimal(str(total)))

    context = {
        'invoice': invoice,
        'seller': seller,
        'services_with_totals': services_with_totals,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'subtotal_after_discount': subtotal_after_discount,
        'tva_amount': tva_amount,
        'total_fodec': total_fodec,
        'total': total,
        'total_in_words': total_in_words,
        'invoiceCurrency': invoice_currency,
    }

    html_string = render_to_string('sales/invoice_pdf.html', context)
    pdf_bytes = HTML(string=html_string).write_pdf()
    return pdf_bytes


def render_avoir_pdf(credit_note, seller):
    """Render a credit note (avoir) to PDF bytes using WeasyPrint."""
    from sales.utilities import num2words_tnd_fr

    total = credit_note.calculate_total()
    total_in_words = num2words_tnd_fr(Decimal(str(total)))

    context = {
        'avoir': credit_note,
        'seller': seller,
        'total_in_words': total_in_words,
    }

    html_string = render_to_string('sales/avoir_pdf.html', context)
    pdf_bytes = HTML(string=html_string).write_pdf()
    return pdf_bytes
