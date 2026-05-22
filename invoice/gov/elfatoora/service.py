"""Service layer for elfatoora — Stage 2 delivery of signed invoices to TTN."""
import logging
from django.db import connection
from django.utils import timezone

from gov.elfatoora import client
from gov.elfatoora.client import ElfatooraError

logger = logging.getLogger(__name__)


class ElfatooraNotReadyError(Exception):
    """GovInvoice has no signed_xml — stage 1 not complete."""


class ElfatooraNotConfiguredError(Exception):
    """No active ElfatooraClientAccount for this tenant."""


def _get_account():
    """Load ElfatooraClientAccount for the current tenant from public schema."""
    from tenants.models import Tenant, ElfatooraClientAccount
    current_schema = connection.schema_name
    try:
        connection.set_schema_to_public()
        tenant = Tenant.objects.get(schema_name=current_schema)
        return ElfatooraClientAccount.objects.filter(tenant=tenant).first()
    finally:
        connection.set_schema(current_schema)


def _credentials():
    account = _get_account()
    if not account or account.status == 'ERROR':
        raise ElfatooraNotConfiguredError(
            'Elfatoora non configuré pour ce tenant. '
            'Veuillez compléter username/password/mf.'
        )
    if not (account.username and account.password and account.mf):
        raise ElfatooraNotConfiguredError(
            'Identifiants elfatoora incomplets pour ce tenant.'
        )
    return account.username, account.password, account.mf


def submit(gov_invoice):
    """Push the signed XML to TTN via elfatoora SOAP.

    Pre-condition: gov_invoice.signed_xml is non-empty (NGSign stage finished).
    Stores generatedRef and flips elfatoora_status to SUBMITTED.
    """
    if not gov_invoice.signed_xml:
        raise ElfatooraNotReadyError(
            f'GovInvoice {gov_invoice.id} has no signed_xml; complete NGSign first.'
        )

    user, password, mf = _credentials()
    try:
        generated_ref = client.save_efact(user, password, mf, bytes(gov_invoice.signed_xml))
    except ElfatooraError as e:
        gov_invoice.elfatoora_status = 'ERROR'
        gov_invoice.elfatoora_last_error = str(e)[:5000]
        gov_invoice.save()
        raise

    gov_invoice.elfatoora_generated_ref = generated_ref
    gov_invoice.elfatoora_status = 'SUBMITTED'
    gov_invoice.elfatoora_submitted_at = timezone.now()
    gov_invoice.elfatoora_last_error = ''
    gov_invoice.status = 'sent'
    gov_invoice.save()
    return generated_ref


def poll(gov_invoice):
    """Query TTN for acknowledgements on a previously submitted invoice.

    Updates elfatoora_status based on whether errors are present in the latest
    acknowledgement. Returns the raw efactCriteria result list from elfatoora.
    """
    if not gov_invoice.elfatoora_generated_ref:
        raise ElfatooraNotReadyError(
            f'GovInvoice {gov_invoice.id} has no elfatoora_generated_ref; submit first.'
        )

    user, password, mf = _credentials()
    results = client.consult_efact(user, password, mf, generated_ref=gov_invoice.elfatoora_generated_ref)
    if not results:
        return results

    latest = results[0]
    acks = getattr(latest, 'listAcknowlegments', None) or []
    if acks:
        last_ack = acks[-1]
        gov_invoice.elfatoora_last_ack_at = getattr(last_ack, 'dateAck', None) or timezone.now()
        errors = getattr(last_ack, 'errors', None) or []
        if errors:
            gov_invoice.elfatoora_status = 'REJECTED'
            gov_invoice.elfatoora_last_error = '; '.join(
                f'{getattr(e, "errorId", "?")}: {getattr(e, "errorDescription", "")}'
                for e in errors
            )[:5000]
            gov_invoice.status = 'rejected'
        else:
            gov_invoice.elfatoora_status = 'ACKNOWLEDGED'
            gov_invoice.elfatoora_last_error = ''
            gov_invoice.status = 'accepted'
        gov_invoice.save()

    return results
