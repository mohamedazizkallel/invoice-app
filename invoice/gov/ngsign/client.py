import base64
import requests
from decouple import config
from gov.ngsign.exceptions import NGSignAuthError, NGSignAPIError, NGSignLockedInvoiceError

INVOICE_API_BASE = 'https://sandbox.ng-sign.com/server'
PARTNER_API_BASE = 'https://sandbox.ng-sign.com'
PDS_BASE = 'https://sandbox.ng-sign.com/pds/#/teif/invoice'
TIMEOUT = 30


def _partner_jwt():
    return config('NGSIGNE_API')


def _auth_headers(jwt):
    return {'Authorization': f'Bearer {jwt}', 'Content-Type': 'application/json'}


def create_org(partner_jwt, name, address, email, first_name=None):
    """Create a new NGSign organization. Returns dict with 'uuid' and 'jwt'."""
    payload = {
        'name': name,
        'street': address,
        'country': 'TN',
        'partnerUser': {
            'email': email,
            'firstName': first_name or name,
            'lastName': '',
            'phoneNumber': '',
        }
    }
    resp = requests.post(
        f'{PARTNER_API_BASE}/protected/user/partner/create',
        json=payload,
        headers=_auth_headers(partner_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'create_org failed: {resp.status_code} — {resp.text}')
    return resp.json()['object']


def update_org(partner_jwt, org_jwt, name, address, email, first_name=None):
    """Update an existing NGSign organization. Returns dict with 'uuid' and 'jwt'."""
    payload = {
        'name': name,
        'street': address,
        'country': 'TN',
        'partnerUser': {
            'email': email,
            'firstName': first_name or name,
            'lastName': '',
            'phoneNumber': '',
        },
        'jwt': org_jwt,
    }
    resp = requests.post(
        f'{PARTNER_API_BASE}/protected/user/partner/update',
        json=payload,
        headers=_auth_headers(partner_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'update_org failed: {resp.status_code} — {resp.text}')
    return resp.json()['object']


def refresh_jwt(partner_jwt, org_uuid):
    """Regenerate JWT for an organization. Returns the new JWT string."""
    resp = requests.post(
        f'{PARTNER_API_BASE}/protected/user/partner/refresh/{org_uuid}',
        headers=_auth_headers(partner_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAuthError(f'refresh_jwt failed: {resp.status_code} — {resp.text}')
    return resp.json()['object']['jwt']


def create_transaction(org_jwt, invoices_payload, signer_email, redirect_url=None):
    """
    Create an e-Signature transaction via /protected/invoice/xml/transaction/create.
    Returns the transaction object dict (contains uuid for PDS redirect).
    """
    body = {
        'invoices': invoices_payload,
        'signerEmail': signer_email,
    }
    if redirect_url:
        body['redirectedTo'] = redirect_url
    resp = requests.post(
        f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create',
        json=body,
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'create_transaction failed: {resp.status_code} — {resp.text}')
    return resp.json()['object']


def get_pds_url(transaction_uuid):
    """Return the PDS (Page de Signature) URL for user redirect."""
    return f'{PDS_BASE}/{transaction_uuid}'


def check_invoice_status(org_jwt, invoice_uuid):
    """Check invoice status. Returns invoice status dict."""
    resp = requests.post(
        f'{INVOICE_API_BASE}/protected/invoice/xml/check/{invoice_uuid}',
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        try:
            body = resp.json()
            if body.get('errorCode') == 50010:
                raise NGSignLockedInvoiceError('Invoice is locked — already processed by TTN.')
        except (ValueError, KeyError):
            pass
        raise NGSignAPIError(f'check_invoice_status failed: {resp.status_code}')
    return resp.json()['object']


def get_signed_xml(org_jwt, invoice_uuid):
    """Download signed XML for an invoice. Returns raw XML bytes."""
    resp = requests.get(
        f'{INVOICE_API_BASE}/protected/invoice/xml/xml/{invoice_uuid}',
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'get_signed_xml failed: {resp.status_code}')
    b64_content = resp.json()['object']
    return base64.b64decode(b64_content)
