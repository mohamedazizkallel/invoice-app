"""
elfatoora (TTN) SOAP client — Stage 2 of the e-invoice pipeline.

Stage 1 (signing) is handled by `invoice/gov/ngsign/`. Once a GovInvoice has
`signed_xml`, this module pushes that XML to TTN via the EfactService SOAP API
and polls for acknowledgements.

WSDL ops:
    saveEfact(user, password, mf, signedXmlB64)       -> generatedRef (str)
    consultEfact(user, password, mf, efactCriteria)   -> list[efactCriteria]

The `arg0..arg3` names in the WSDL are JAX-WS defaults; mapping to
(user, password, mf, payload) follows TTN/elfatoora convention.

Credentials are passed in by the caller because they are per-tenant
(`ElfatooraClientAccount`). Only deployment-level settings (WSDL URL, SOCKS
proxy) come from env.
"""
import base64
from decouple import config
from zeep import Client, Settings
from zeep.transports import Transport
from requests import Session


class ElfatooraError(Exception):
    """Wrap any elfatoora-side failure (transport, SOAP fault, business error)."""


def _session():
    """Build a requests Session, optionally routed through a SOCKS5 proxy.

    Dev/test machines often sit outside the TTN whitelist, so we tunnel via a
    whitelisted VPS. Production sets ELFATOORA_SOCKS_PROXY="" to go direct.
    """
    s = Session()
    proxy = config('ELFATOORA_SOCKS_PROXY', default='')
    if proxy:
        s.proxies = {'http': proxy, 'https': proxy}
    return s


def _client():
    wsdl = config('ELFATOORA_WSDL')
    transport = Transport(session=_session(), timeout=30, operation_timeout=60)
    settings = Settings(strict=False, xml_huge_tree=True)
    return Client(wsdl=wsdl, transport=transport, settings=settings)


def save_efact(user, password, mf, signed_xml_bytes):
    """Push a signed TEIF XML to TTN. Returns the generatedRef string."""
    payload_b64 = base64.b64encode(signed_xml_bytes).decode()
    try:
        return _client().service.saveEfact(user, password, mf, payload_b64)
    except Exception as e:
        raise ElfatooraError(f'saveEfact failed: {e}') from e


def consult_efact(user, password, mf, generated_ref=None, document_number=None):
    """Query TTN for the status of a previously submitted invoice.

    Either `generated_ref` (returned by save_efact) or `document_number` can be
    used as the filter key.
    """
    client = _client()
    criteria_type = client.get_type('ns0:efactCriteria')
    criteria = criteria_type(
        generatedRef=generated_ref,
        documentNumber=document_number,
    )
    try:
        return client.service.consultEfact(user, password, mf, criteria)
    except Exception as e:
        raise ElfatooraError(f'consultEfact failed: {e}') from e
