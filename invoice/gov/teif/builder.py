from sales.models import Invoice, Settings
from lxml import etree
from datetime import datetime

from .namespaces import (
    NAMESPACE_MAP,
    TEIF_VERSION,
    CONTROLLING_AGENCY,
    teif,
)


def _build_invoice_header(parent, seller, client):
    """Build the invoice header with sender/receiver identifiers"""
    header = etree.SubElement(parent, teif("InvoiceHeader"))

    # Sender identifier with mandatory type attribute
    etree.SubElement(
        header,
        teif("MessageSenderIdentifier"),
        type="I-01"  # Matricule Fiscal type
    ).text = seller.mf

    # Receiver identifier with mandatory type attribute (note typo in schema: Reciever not Receiver)
    etree.SubElement(
        header,
        teif("MessageRecieverIdentifier"),  # Schema has typo: Reciever
        type="I-01"  # Matricule Fiscal type
    ).text = client.mf

    return header


def _build_bgm(parent, invoice):
    """Build Beginning of Message section with correct tags"""
    bgm = etree.SubElement(parent, teif("Bgm"))

    # DocumentIdentifier comes first
    etree.SubElement(
        bgm, 
        teif("DocumentIdentifier")
    ).text = invoice.uniqueId
    
    # DocumentType with code attribute and content
    etree.SubElement(
        bgm, 
        teif("DocumentType"),
        code="I-11"
    ).text = "Facture"  # Must have content per schema


def _build_dtm(parent, invoice):
    """Build Date/Time section with correct format"""
    dtm_issue = etree.SubElement(parent, teif("Dtm"))
    
    # Use DateText with functionCode and format attributes (lowercase ddMMyy per schema)
    etree.SubElement(
        dtm_issue, 
        teif("DateText"),
        functionCode="I-31",  # Issuance date
        format="ddMMyy"  # Must be lowercase per schema
    ).text = invoice.date_created.strftime("%d%m%y")


def _build_partner_details(parent, name, tax_id, address, function_code):
    """Build PartnerDetails block with Nad structure"""
    partner = etree.SubElement(
        parent, 
        teif("PartnerDetails"),
        functionCode=function_code
    )
    
    # Name and Address block
    nad = etree.SubElement(partner, teif("Nad"))
    
    # PartnerIdentifier with type attribute
    etree.SubElement(
        nad, 
        teif("PartnerIdentifier"),
        type="I-01"
    ).text = tax_id
    
    # PartnerName (not PartnerNom per schema)
    etree.SubElement(
        nad, 
        teif("PartnerName"),
        nameType="Physical"
    ).text = name
    
    # PartnerAdresses
    partner_addresses = etree.SubElement(nad, teif("PartnerAdresses"))
    etree.SubElement(partner_addresses, teif("AdressDescription")).text = address
    etree.SubElement(partner_addresses, teif("Country"), codeList="ISO_3166-1").text = "TN"


def _build_partner_section(parent, invoice, seller):
    """Build the partner section with correct structure"""
    ps = etree.SubElement(parent, teif("PartnerSection"))

    # Supplier (I-62)
    _build_partner_details(
        ps,
        name=seller.clientname,
        tax_id=seller.mf,
        address=seller.adress,
        function_code="I-62"
    )
    
    # Client (I-64)
    _build_partner_details(
        ps,
        name=invoice.client.clientname,
        tax_id=invoice.client.mf,
        address=invoice.client.adress,
        function_code="I-64"
    )


def _build_lin_section(parent, invoice):
    """Build line items section with correct quantity format"""
    lin_section = etree.SubElement(parent, teif("LinSection"))

    lines = invoice.invoice_services.select_related('service').all().order_by("id")

    for idx, line in enumerate(lines, start=1):
        lin = etree.SubElement(lin_section, teif("Lin"))

        # Item identifier (instead of LinNum)
        etree.SubElement(lin, teif("ItemIdentifier")).text = str(idx)

        # Description
        description = line.service.description or line.service.title
        etree.SubElement(lin, teif("LinImd")).text = description

        # Quantity with measurementUnit attribute
        qty = etree.SubElement(lin, teif("LinQty"))
        
        # Determine quantity and unit based on billing type
        if line.service.billing_type == 'hour':
            quantity = line.hours_used or 1
            unit_code = "HUR"
        elif line.service.billing_type == 'day':
            quantity = line.days_used or 1
            unit_code = "DAY"
        else:  # flat
            quantity = 1
            unit_code = "C62"
            
        etree.SubElement(
            qty, 
            teif("Quantity"),
            measurementUnit=unit_code
        ).text = str(quantity)

        # Tax (TVA)
        tax = etree.SubElement(lin, teif("LinTax"))

        etree.SubElement(
            tax,
            teif("TaxTypeName"),
            code="I-1602"
        )

        tax_details = etree.SubElement(tax, teif("TaxDetails"))
        etree.SubElement(tax_details, teif("TaxRate")).text = f"{invoice.get_tva():.2f}"

        # Line total with MoaDetails wrapper
        lin_moa = etree.SubElement(lin, teif("LinMoa"))
        moa_details = etree.SubElement(lin_moa, teif("MoaDetails"))
        moa = etree.SubElement(
            moa_details,
            teif("Moa"),
            currencyCodeList="ISO_4217",
            amountTypeCode="I-180"
        )
        amount = etree.SubElement(moa, teif("Amount"), currencyIdentifier="TND")
        amount.text = f"{line.get_line_total():.3f}"


def _build_invoice_alc(parent, invoice):
    """Build global invoice discount section if discount exists"""
    discount_amount = invoice.calculate_discount_amount()
    
    if discount_amount > 0:
        alc_section = etree.SubElement(parent, teif("InvoiceAlc"))
        
        # AllowanceDetails wrapper (required)
        allowance_details = etree.SubElement(alc_section, teif("AllowanceDetails"))
        
        # Alc block with discount type code (note: allowanceCode not code per schema)
        alc = etree.SubElement(
            allowance_details,
            teif("Alc"),
            allowanceCode="I-151"  # I-151: Standard discount, I-152: Rebate, I-153: Allowance
        )
        
        # Moa with proper structure per schema
        moa = etree.SubElement(
            allowance_details,
            teif("Moa"),
            currencyCodeList="ISO_4217",
            amountTypeCode="I-151"
        )
        amount = etree.SubElement(moa, teif("Amount"), currencyIdentifier="TND")
        amount.text = f"{discount_amount:.3f}"
        
        # Optional: Free text description
        if invoice.discount:
            ftx = etree.SubElement(allowance_details, teif("Ftx"))
            ftx_detail = etree.SubElement(ftx, teif("FreeTextDetail"), subjectCode="I-41")
            etree.SubElement(ftx_detail, teif("FreeTexts")).text = f"Remise de {invoice.discount}%"


def _build_invoice_tax(parent, invoice):
    """Build mandatory invoice-level tax summary section"""
    tax_section = etree.SubElement(parent, teif("InvoiceTax"))
    
    # InvoiceTaxDetails wrapper (required)
    tax_details = etree.SubElement(tax_section, teif("InvoiceTaxDetails"))
    
    # Tax block
    tax = etree.SubElement(tax_details, teif("Tax"))
    
    # Tax type
    etree.SubElement(
        tax,
        teif("TaxTypeName"),
        code="I-1602"  # TVA code
    ).text = "TVA"
    
    # Tax details with rate
    tax_rate_details = etree.SubElement(tax, teif("TaxDetails"))
    etree.SubElement(tax_rate_details, teif("TaxRate")).text = f"{invoice.get_tva():.2f}"
    
    # AmountDetails wrapper for tax amounts
    amount_details = etree.SubElement(tax_details, teif("AmountDetails"))
    
    # Moa for taxable base
    moa_base = etree.SubElement(amount_details, teif("MoaDetails"))
    etree.SubElement(
        moa_base,
        teif("Moa"),
        currencyCodeList="ISO_4217",
        amountTypeCode="I-171"  # Taxable base
    )
    amount_base = etree.SubElement(moa_base.find(teif("Moa")), teif("Amount"), currencyIdentifier="TND")
    amount_base.text = f"{invoice.calculate_subtotal_after_discount():.3f}"
    
    # Moa for tax amount
    moa_tax = etree.SubElement(amount_details, teif("MoaDetails"))
    etree.SubElement(
        moa_tax,
        teif("Moa"),
        currencyCodeList="ISO_4217",
        amountTypeCode="I-176"  # Tax amount
    )
    amount_tax = etree.SubElement(moa_tax.find(teif("Moa")), teif("Amount"), currencyIdentifier="TND")
    amount_tax.text = f"{invoice.calculate_tva_amount():.3f}"


def _build_invoice_totals(parent, invoice):
    """Build invoice monetary totals using Moa with amountTypeCode"""
    moa_section = etree.SubElement(parent, teif("InvoiceMoa"))
    
    # AmountDetails wrapper (required)
    amount_details = etree.SubElement(moa_section, teif("AmountDetails"))
    
    # Helper function to create Moa with proper structure
    def add_moa(parent, amount_code, amount_value):
        moa_details = etree.SubElement(parent, teif("MoaDetails"))
        moa = etree.SubElement(
            moa_details,
            teif("Moa"),
            currencyCodeList="ISO_4217",
            amountTypeCode=amount_code
        )
        amount_el = etree.SubElement(moa, teif("Amount"), currencyIdentifier="TND")
        amount_el.text = f"{amount_value:.3f}"

    # Total HT BEFORE discount (I-172)
    add_moa(amount_details, "I-172", invoice.calculate_service_subtotal())
    
    # TVA amount (I-176)
    add_moa(amount_details, "I-176", invoice.calculate_tva_amount())
    
    # Timbre Fiscal (I-177)
    add_moa(amount_details, "I-177", invoice.get_timbre_fiscal())
    
    # Total TTC (I-180)
    add_moa(amount_details, "I-180", invoice.calculate_total())


def _build_ref_ttn_val(parent):
    """Build reference TTN validation placeholder"""
    etree.SubElement(parent, teif("RefTtnVal"))


def _build_invoice_body(parent, invoice, seller):
    """Build the complete invoice body"""
    body = etree.SubElement(parent, teif("InvoiceBody"))

    _build_bgm(body, invoice)
    _build_dtm(body, invoice)
    _build_partner_section(body, invoice, seller)
    _build_lin_section(body, invoice)
    _build_invoice_alc(body, invoice)  # Discount section (if applicable)
    _build_invoice_tax(body, invoice)  # Mandatory tax summary
    _build_invoice_totals(body, invoice)

    return body


def build_unsigned_teif(invoice: Invoice, seller: Settings) -> bytes:
    """
    Build unsigned TEIF XML document for e-invoicing.
    
    Returns XML as single-line UTF-8 bytes without BOM.
    XAdES-B signature with Id="SigFrs" must be added as last child after this.
    
    Args:
        invoice: Invoice instance to export
        seller: Settings instance with seller information
        
    Returns:
        bytes: XML document as UTF-8 encoded bytes (pretty formatted)
        
    Raises:
        ValueError: If invoice or seller data is invalid
    """
    # Validate inputs
    if not invoice.client:
        raise ValueError("Invoice must have a client assigned")
    
    if not invoice.uniqueId:
        raise ValueError("Invoice must have a uniqueId")
    
    if not seller.mf or not invoice.client.mf:
        raise ValueError("Both seller and client must have MF (Matricule Fiscal)")
    
    # Create fresh root element for this invoice
    root = etree.Element(
        teif("TEIF"),
        nsmap=NAMESPACE_MAP,
        version=TEIF_VERSION,
        controlingAgency=CONTROLLING_AGENCY,  # Note: single 'l' per schema
    )

    # Build document structure
    _build_invoice_header(root, seller, invoice.client)
    _build_invoice_body(root, invoice, seller)
    _build_ref_ttn_val(root)

    # Return pretty formatted XML (will be condensed before signing)
    xml_bytes = etree.tostring(
        root,
        encoding='utf-8',
        xml_declaration=True,
        pretty_print=True
    )
    
    return xml_bytes


def condense_to_single_line(xml_bytes: bytes) -> bytes:
    """
    Convert XML to single-line format required before signing.
    Removes all whitespace between tags while preserving content.
    """
    import re
    xml_str = xml_bytes.decode('utf-8')
    
    # Remove all newlines and carriage returns
    single_line = xml_str.replace('\n', '').replace('\r', '')
    
    # Remove extra spaces between tags
    single_line = re.sub(r'>\s+<', '><', single_line)
    
    return single_line.encode('utf-8')


def inject_signature(unsigned_xml: bytes, signature_element: etree._Element) -> bytes:
    """
    Inject XAdES-B ds:Signature with Id="SigFrs" as last child of TEIF root.
    
    CRITICAL: No mutations allowed after this operation.
    
    Args:
        unsigned_xml: The unsigned XML document (must be single-line)
        signature_element: The <ds:Signature Id="SigFrs">...</ds:Signature> element
        
    Returns:
        bytes: Signed XML document (single-line)
    """
    root = etree.fromstring(unsigned_xml)
    
    # Verify signature has required Id attribute
    if signature_element.get('Id') != 'SigFrs':
        raise ValueError("Signature must have Id='SigFrs' attribute")
    
    # Append as last child
    root.append(signature_element)
    
    # Return as single-line XML
    xml_bytes = etree.tostring(
        root,
        encoding='utf-8',
        xml_declaration=True
    )
    
    return condense_to_single_line(xml_bytes)