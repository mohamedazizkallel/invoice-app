import base64
import requests
from decouple import config
from gov.ngsign.exceptions import NGSignAuthError, NGSignAPIError

INVOICE_API_BASE = 'https://sandbox.ng-sign.com/server'
PARTNER_API_BASE = 'https://sandbox.ng-sign.com'
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


def test_connectivity(org_jwt, org_uuid, partner_jwt):
    """
    Verify org JWT is valid. Auto-refreshes on 401.
    Returns True if valid, or the new JWT string if refreshed.
    Raises NGSignAuthError if refresh also fails.
    """
    resp = requests.get(
        f'{INVOICE_API_BASE}/protected/invoice/status',
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code == 200:
        return True
    if resp.status_code == 401:
        try:
            new_jwt = refresh_jwt(partner_jwt, org_uuid)
        except NGSignAuthError:
            raise NGSignAuthError('JWT invalide et rafraîchissement échoué.')
        retry = requests.get(
            f'{INVOICE_API_BASE}/protected/invoice/status',
            headers=_auth_headers(new_jwt),
            timeout=TIMEOUT,
        )
        if retry.status_code == 200:
            return new_jwt
        raise NGSignAuthError('JWT invalide après rafraîchissement.')
    raise NGSignAPIError(f'test_connectivity unexpected status: {resp.status_code}')


def submit_seal(org_jwt, invoices_payload):
    """Submit invoices for Seal signing. Returns transaction object dict."""
    body = {
        'invoices': invoices_payload,
        'notifyOwner': False,
        'sendToSigner': False,
    }
    resp = requests.post(
        f'{INVOICE_API_BASE}/protected/invoice/v2/transaction/seal',
        json=body,
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'submit_seal failed: {resp.status_code} — {resp.text}')
    return resp.json()['object']


def get_signed_xml(org_jwt, invoice_uuid):
    """Download signed XML for an invoice. Returns raw XML bytes."""
    resp = requests.get(
        f'{INVOICE_API_BASE}/protected/invoice/xml/{invoice_uuid}',
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'get_signed_xml failed: {resp.status_code}')
    b64_content = resp.json()['object']
    return base64.b64decode(b64_content)


def check_ttn_status(org_jwt, invoice_uuid):
    """Force TTN status sync. Returns invoice status dict."""
    resp = requests.post(
        f'{INVOICE_API_BASE}/protected/invoice/check/{invoice_uuid}',
        headers=_auth_headers(org_jwt),
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NGSignAPIError(f'check_ttn_status failed: {resp.status_code}')
    return resp.json()['object']
