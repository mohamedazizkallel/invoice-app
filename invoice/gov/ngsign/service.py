import logging
from django.utils import timezone
from django.db import connection

from gov.ngsign import client
from gov.ngsign import serializer
from decouple import config
from gov.ngsign.exceptions import (
    NGSignNotConfiguredError, NGSignAuthError, NGSignAPIError, NGSignSubmissionError
)

logger = logging.getLogger(__name__)


def _get_account():
    """Load NGSignClientAccount for the current tenant from public schema."""
    from tenants.models import Tenant, NGSignClientAccount
    current_schema = connection.schema_name
    try:
        connection.set_schema_to_public()
        tenant = Tenant.objects.get(schema_name=current_schema)
        return NGSignClientAccount.objects.filter(tenant=tenant).first()
    finally:
        connection.set_schema(current_schema)


def verify_account(account):
    """
    Run connectivity check, auto-refreshing JWT if needed.
    Updates account in-place and saves.
    """
    partner_jwt = config('NGSIGNE_API')
    result = client.test_connectivity(account.org_jwt, account.org_uuid, partner_jwt)
    if result is not True:
        account.org_jwt = result
    account.status = 'ACTIVE'
    account.last_verified_at = timezone.now()
    # Save to public schema
    current_schema = connection.schema_name
    try:
        connection.set_schema_to_public()
        account.save()
    finally:
        connection.set_schema(current_schema)


def submit_invoice(gov_invoice):
    """
    Sign a GovInvoice using NGSign Seal.
    On success: stores signed_xml, ngsign UUIDs, sets status='signed'.
    On failure: raises NGSignSubmissionError.
    """
    account = _get_account()
    if not account or account.status == 'ERROR':
        raise NGSignNotConfiguredError(
            'NGSign non configuré pour ce tenant. '
            'Veuillez compléter vos paramètres.'
        )

    # Connectivity check + auto-refresh
    try:
        verify_account(account)
    except NGSignAuthError as e:
        raise NGSignNotConfiguredError(f'Authentification NGSign échouée: {e}')

    # Build payload
    payload = serializer.build_payload(gov_invoice)

    # Submit
    try:
        txn = client.submit_seal(account.org_jwt, [payload])
    except NGSignAPIError as e:
        gov_invoice.ngsign_status = 'ERROR'
        gov_invoice.save()
        raise NGSignSubmissionError(str(e))

    # Store transaction info
    gov_invoice.ngsign_transaction_uuid = txn['uuid']
    invoice_info = txn['invoices'][0]
    gov_invoice.ngsign_invoice_uuid = invoice_info['uuid']
    gov_invoice.ngsign_status = invoice_info['status']

    # Fetch signed XML
    try:
        signed_xml = client.get_signed_xml(account.org_jwt, invoice_info['uuid'])
        gov_invoice.signed_xml = signed_xml
        gov_invoice.status = 'signed'
    except NGSignAPIError as e:
        logger.warning(f'Signed XML fetch failed for {invoice_info["uuid"]}: {e}')

    gov_invoice.save()
    return txn
