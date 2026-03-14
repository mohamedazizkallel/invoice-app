import base64
from decimal import Decimal
from sales.models import Settings


UNIT_MAP = {
    'flat': ('C62', lambda svc: 1),
    'unit': ('C62', lambda svc: svc.units_used or 1),
    'hour': ('HUR', lambda svc: svc.hours_used or 1),
    'day':  ('DAY', lambda svc: svc.days_used or 1),
}


def _address(description):
    return {
        'description': description or '',
        'street': '',
        'cityName': '',
        'postalCode': '',
        'country': 'TN',
    }


def _item_taxes(invoice_service, tva_rate):
    line_ht = invoice_service.get_line_ht()
    tva_amount = line_ht * (tva_rate / Decimal('100'))
    taxes = [
        {
            'code': 'I-1602',
            'taxRate': str(tva_rate),
            'amount': float(tva_amount.quantize(Decimal('0.001'))),
            'amountBase': float(line_ht.quantize(Decimal('0.001'))),
        }
    ]
    fodec = invoice_service.get_fodec_amount()
    if fodec > 0:
        taxes.append({
            'code': 'FODEC',
            'taxRate': '1.0',
            'amount': float(fodec.quantize(Decimal('0.001'))),
            'amountBase': float(line_ht.quantize(Decimal('0.001'))),
        })
    return taxes


def _build_item(invoice_service, tva_rate):
    billing_type = invoice_service.service.billing_type
    unit_code, qty_fn = UNIT_MAP.get(billing_type, UNIT_MAP['flat'])
    return {
        'name': invoice_service.service.title,
        'code': invoice_service.service.uniqueId,
        'unit': unit_code,
        'quantity': qty_fn(invoice_service),
        'tvaRate': float(tva_rate),
        'unitPrice': float(invoice_service.unit_price),
        'totalPrice': float(invoice_service.get_line_ht()),
        'taxes': _item_taxes(invoice_service, tva_rate),
    }


def build_payload(gov_invoice):
    invoice = gov_invoice.invoice
    settings = Settings.get_cached()
    client = invoice.client
    tva_rate = invoice.get_tva()

    tief = {
        'documentIdentifier': invoice.title or invoice.uniqueId,
        'documentType': 'I-11',
        'invoiceDate': invoice.date_created.isoformat(),
        'currencyIdentifier': 'TND',

        'supplierIdentifier': settings.mf,
        'supplierDetails': {
            'partnerIdentifier': settings.mf,
            'partnerName': settings.clientname,
            'address': _address(settings.adress),
        },

        'clientIdentifier': client.mf,
        'clientDetails': {
            'partnerIdentifier': client.mf,
            'partnerName': client.clientname,
            'address': _address(client.adress),
        },

        'items': [
            _build_item(svc, tva_rate)
            for svc in invoice.invoice_services.all()
        ],

        'invoiceTotalWithoutTax': float(invoice.calculate_service_subtotal()),
        'invoiceTotalTax': float(invoice.calculate_tva_amount()),
        'invoiceTotalWithTax': float(invoice.calculate_total()),

        'taxes': [
            {
                'code': 'I-1602',
                'taxRate': str(tva_rate),
                'amount': float(invoice.calculate_tva_amount()),
                'amountBase': float(invoice.calculate_service_subtotal()),
            }
        ],
    }

    return {
        'type': 'I_11',
        'invoiceFileB64': base64.b64encode(bytes(gov_invoice.unsigned_xml)).decode(),
        'configuration': {
            'allPages': True,
            'qrPositionX': 0,
            'qrPositionY': 0,
            'qrPositionP': 0,
        },
        'invoiceTIEF': tief,
        'clientEmail': getattr(client, 'emailAddress', None) or '',
    }
