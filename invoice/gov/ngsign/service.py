import logging
from django.db import connection

from gov.ngsign import client
from gov.ngsign import serializer
from gov.ngsign.exceptions import (
    NGSignNotConfiguredError, NGSignAPIError, NGSignSubmissionError, NGSignLockedInvoiceError
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


def submit_invoice(gov_invoice, redirect_url=None):
    """
    Create an e-Signature transaction for a GovInvoice.
    Returns the PDS redirect URL for the user to sign.
    """
    account = _get_account()
    if not account or account.status == 'ERROR':
        raise NGSignNotConfiguredError(
            'NGSign non configuré pour ce tenant. '
            'Veuillez compléter vos paramètres.'
        )

    # Build payload (XML + PDF)
    payload = serializer.build_payload(gov_invoice)

    # Signer email must be the NGSign partner account email
    signer_email = account.signer_email
    if not signer_email:
        raise NGSignNotConfiguredError(
            'Email du signataire NGSign non configuré. '
            'Veuillez renseigner le champ signer_email dans NGSignClientAccount.'
        )

    # Create transaction
    try:
        txn = client.create_transaction(
            account.org_jwt,
            [payload],
            signer_email=signer_email,
            redirect_url=redirect_url,
        )
    except NGSignAPIError as e:
        gov_invoice.ngsign_status = 'ERROR'
        gov_invoice.save()
        raise NGSignSubmissionError(str(e))

    # Store transaction info
    gov_invoice.ngsign_transaction_uuid = txn['uuid']
    invoice_info = txn['invoices'][0]
    gov_invoice.ngsign_invoice_uuid = invoice_info['uuid']
    gov_invoice.ngsign_status = invoice_info.get('status', 'CREATED')
    gov_invoice.save()

    # Return PDS URL for redirect
    return client.get_pds_url(txn['uuid'])


def check_status(gov_invoice):
    """
    Check the current status of an invoice in NGSign.
    Updates gov_invoice fields and returns the status dict.
    """
    account = _get_account()
    if not account:
        raise NGSignNotConfiguredError('NGSign non configuré.')

    try:
        result = client.check_invoice_status(account.org_jwt, gov_invoice.ngsign_invoice_uuid)
    except NGSignLockedInvoiceError:
        # Invoice locked = already processed by TTN. Fetch signed XML directly.
        logger.info(f'GovInvoice {gov_invoice.id} is locked — fetching signed XML directly.')
        try:
            signed_xml = client.get_signed_xml(account.org_jwt, gov_invoice.ngsign_invoice_uuid)
            gov_invoice.signed_xml = signed_xml
            gov_invoice.status = 'signed'
        except NGSignAPIError as e:
            logger.warning(f'Signed XML fetch failed for locked invoice: {e}')
        gov_invoice.ngsign_status = 'TTN_SIGNED'
        gov_invoice.save()
        return {'status': 'TTN_SIGNED'}

    gov_invoice.ngsign_status = result['status']

    # If signed by TTN, fetch the signed XML
    if result['status'] in ('TTN_SIGNED', 'TTN_TRANSFERED'):
        try:
            signed_xml = client.get_signed_xml(account.org_jwt, gov_invoice.ngsign_invoice_uuid)
            gov_invoice.signed_xml = signed_xml
            gov_invoice.status = 'signed'
        except NGSignAPIError as e:
            logger.warning(f'Signed XML fetch failed: {e}')

    gov_invoice.save()
    return result
