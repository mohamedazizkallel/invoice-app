import zeep
from zeep.transports import Transport
from requests import Session
from requests.auth import HTTPBasicAuth
from sales.models import Invoice, Settings

ELFATOORA_WSDL = "https://elfatoora.tn/ElfatouraServices/EfactService?wsdl"

def get_soap_client(username: str, password: str):
    session = Session()
    session.auth = HTTPBasicAuth(username, password)
    session.verify = True
    transport = Transport(session=session, timeout=30)
    return zeep.Client(wsdl=ELFATOORA_WSDL, transport=transport)

def submit_invoice(invoice: Invoice, seller: Settings, username: str, password: str):
    client = get_soap_client(username, password)
    
    if not hasattr(invoice, 'signed_xml') or not invoice.signed_xml:
        raise ValueError("Invoice must be signed first")

    xml_str = invoice.signed_xml.decode("utf-8")

    response = client.service.saveEfact(
        login=username,
        password=password,
        matriculeFiscal=seller.mf,  # Seller's MF
        xml=xml_str
    )

    # Save response
    invoice.soap_response = str(response)
    invoice.status = "PAID" if getattr(response, "success", False) else "CURRENT"
    invoice.save()

    return response

def consult_invoice(invoice: Invoice, seller: Settings, username: str, password: str):
    client = get_soap_client(username, password)

    response = client.service.consultEfact(
        login=username,
        password=password,
        matriculeFiscal=seller.mf,
        serialNumber=invoice.uniqueId  # Use invoice number
    )

    invoice.soap_response = str(response)
    invoice.save()

    return response