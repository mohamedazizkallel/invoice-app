import re

from sales.models import Invoice, CreditNote, Settings
from lxml import etree
from datetime import datetime

from .namespaces import (
    NAMESPACE_MAP,
    TEIF_VERSION,
    CONTROLLING_AGENCY,
    teif,
)

# Characters that TTN rejects in text content
_FORBIDDEN_CHARS = re.compile(r'[%/\\<>&\"\']')


def _build_invoice_header(parent, seller, client):
    """Build the invoice header with sender/receiver identifiers"""
    header = etree.SubElement(parent, teif("InvoiceHeader"))

    # Sender identifier with mandatory type attribute
    etree.SubElement(
        header,
        teif("MessageSenderIdentifier"),
        type="I-01"  # Matricule Fiscal type
    ).text = _clean_mf(seller.mf)

    # Receiver identifier with mandatory type attribute (note typo in schema: Reciever not Receiver)
    etree.SubElement(
        header,
        teif("MessageRecieverIdentifier"),  # Schema has typo: Reciever
        type="I-01"  # Matricule Fiscal type
    ).text = _clean_mf(client.mf)

    return header


def _build_bgm(parent, doc, doc_type="I-11", doc_label="Facture"):
    """Build Beginning of Message section with correct tags"""
    bgm = etree.SubElement(parent, teif("Bgm"))

    etree.SubElement(
        bgm,
        teif("DocumentIdentifier")
    ).text = doc.uniqueId

    etree.SubElement(
        bgm,
        teif("DocumentType"),
        code=doc_type
    ).text = doc_label


def _build_dtm(parent, doc):
    """Build Date/Time section with correct format"""
    dtm_issue = etree.SubElement(parent, teif("Dtm"))

    etree.SubElement(
        dtm_issue,
        teif("DateText"),
        functionCode="I-31",
        format="ddMMyy"
    ).text = doc.date_created.strftime("%d%m%y")


def _clean_mf(mf: str) -> str:
    """Strip slashes from Matricule Fiscal — TTN rejects MF values containing '/'"""
    return mf.replace("/", "")


def _sanitize(text: str) -> str:
    """Remove special characters that TTN rejects (%, /, etc.)"""
    if not text:
        return text
    return _FORBIDDEN_CHARS.sub('', text)


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
    ).text = _clean_mf(tax_id)
    
    # PartnerName with nameType: Physical or Qualification per schema
    etree.SubElement(
        nad,
        teif("PartnerName"),
        nameType="Physical"
    ).text = _sanitize(name)
    
    # PartnerAdresses
    partner_addresses = etree.SubElement(nad, teif("PartnerAdresses"))
    etree.SubElement(partner_addresses, teif("AdressDescription")).text = _sanitize(address)
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

        # Description (ImdType requires ItemCode + ItemDescription children)
        description = line.service.description or line.service.title
        lin_imd = etree.SubElement(lin, teif("LinImd"))
        etree.SubElement(lin_imd, teif("ItemCode")).text = str(line.service.id)
        etree.SubElement(lin_imd, teif("ItemDescription")).text = _sanitize(description)

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
        ).text = "TVA"  # NotNullDataStringType_200 requires non-empty text

        tax_details = etree.SubElement(tax, teif("TaxDetails"))
        etree.SubElement(tax_details, teif("TaxRate")).text = f"{invoice.get_tva():.2f}"

        # Line total with MoaDetails wrapper
        lin_moa = etree.SubElement(lin, teif("LinMoa"))
        moa_details = etree.SubElement(lin_moa, teif("MoaDetails"))
        moa = etree.SubElement(
            moa_details,
            teif("Moa"),
            currencyCodeList="ISO_4217",
            amountTypeCode="I-171"  # Montant total HT de l'article
        )
        amount = etree.SubElement(moa, teif("Amount"), currencyIdentifier="TND")
        amount.text = f"{line.get_line_ht():.3f}"


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
            amountTypeCode="I-173"  # Montant total de la remise globale facture
        )
        amount = etree.SubElement(moa, teif("Amount"), currencyIdentifier="TND")
        amount.text = f"{discount_amount:.3f}"
        
        # Optional: Free text description
        if invoice.discount:
            ftx = etree.SubElement(allowance_details, teif("Ftx"))
            ftx_detail = etree.SubElement(ftx, teif("FreeTextDetail"), subjectCode="I-41")
            etree.SubElement(ftx_detail, teif("FreeTexts")).text = f"Remise de {invoice.discount} pct"


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
    
    # Each AmountDetails IS a MoaDetailsType — Moa goes directly inside it
    # Taxable base
    ad_base = etree.SubElement(tax_details, teif("AmountDetails"))
    moa_base = etree.SubElement(
        ad_base,
        teif("Moa"),
        currencyCodeList="ISO_4217",
        amountTypeCode="I-177"  # Montant base taxe
    )
    etree.SubElement(moa_base, teif("Amount"), currencyIdentifier="TND").text = \
        f"{invoice.calculate_subtotal_after_discount():.3f}"

    # Tax amount
    ad_tax = etree.SubElement(tax_details, teif("AmountDetails"))
    moa_tax = etree.SubElement(
        ad_tax,
        teif("Moa"),
        currencyCodeList="ISO_4217",
        amountTypeCode="I-178"  # Montant Taxe
    )
    etree.SubElement(moa_tax, teif("Amount"), currencyIdentifier="TND").text = \
        f"{invoice.calculate_tva_amount():.3f}"


def _build_invoice_totals(parent, invoice):
    """Build invoice monetary totals using Moa with amountTypeCode"""
    moa_section = etree.SubElement(parent, teif("InvoiceMoa"))

    # MoaInvoiceType: sequence of AmountDetails (each is MoaDetailsType → Moa directly inside)
    def add_moa(amount_code, amount_value):
        ad = etree.SubElement(moa_section, teif("AmountDetails"))
        moa = etree.SubElement(
            ad,
            teif("Moa"),
            currencyCodeList="ISO_4217",
            amountTypeCode=amount_code
        )
        etree.SubElement(moa, teif("Amount"), currencyIdentifier="TND").text = \
            f"{amount_value:.3f}"

    # Total HT BEFORE discount (I-172)
    add_moa("I-172", invoice.calculate_service_subtotal())

    # Total HT AFTER discount (I-176)
    add_moa("I-176", invoice.calculate_subtotal_after_discount())

    # TVA amount (I-181: Montant total Taxe)
    add_moa("I-181", invoice.calculate_tva_amount())

    # Timbre Fiscal (I-179)
    add_moa("I-179", invoice.get_timbre_fiscal())

    # Total TTC (I-180)
    add_moa("I-180", invoice.calculate_total())


def _build_invoice_body(parent, invoice, seller):
    """Build the complete invoice body"""
    body = etree.SubElement(parent, teif("InvoiceBody"))

    # Order must match BodyType sequence in XSD:
    # Bgm, Dtm, PartnerSection, LinSection, InvoiceMoa, InvoiceTax, InvoiceAlc(opt)
    _build_bgm(body, invoice, doc_type="I-11", doc_label="Facture")
    _build_dtm(body, invoice)
    _build_partner_section(body, invoice, seller)
    _build_lin_section(body, invoice)
    _build_invoice_totals(body, invoice)   # InvoiceMoa — must come before InvoiceTax
    _build_invoice_tax(body, invoice)      # InvoiceTax
    _build_invoice_alc(body, invoice)      # InvoiceAlc (optional, must be last)

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
    # RefTtnVal omitted — RefTtnType requires children (ReferenceTTN, ReferenceCEV, ReferenceDate)
    # and is minOccurs="0", so it is only included when TTN reference data is available

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


# ── Credit Note (Avoir) ──

def _build_avoir_lin_section(parent, credit_note):
    """Build line items for a credit note (single line with description + amount)."""
    lin_section = etree.SubElement(parent, teif("LinSection"))
    lin = etree.SubElement(lin_section, teif("Lin"))

    etree.SubElement(lin, teif("ItemIdentifier")).text = "1"

    lin_imd = etree.SubElement(lin, teif("LinImd"))
    etree.SubElement(lin_imd, teif("ItemCode")).text = "AV1"
    etree.SubElement(lin_imd, teif("ItemDescription")).text = _sanitize(credit_note.description)

    qty = etree.SubElement(lin, teif("LinQty"))
    etree.SubElement(qty, teif("Quantity"), measurementUnit="C62").text = "1"

    tax = etree.SubElement(lin, teif("LinTax"))
    etree.SubElement(tax, teif("TaxTypeName"), code="I-1602").text = "TVA"
    tax_details = etree.SubElement(tax, teif("TaxDetails"))
    etree.SubElement(tax_details, teif("TaxRate")).text = f"{credit_note.tva:.2f}"

    lin_moa = etree.SubElement(lin, teif("LinMoa"))
    moa_details = etree.SubElement(lin_moa, teif("MoaDetails"))
    moa = etree.SubElement(
        moa_details, teif("Moa"),
        currencyCodeList="ISO_4217", amountTypeCode="I-171"
    )
    etree.SubElement(moa, teif("Amount"), currencyIdentifier="TND").text = f"{credit_note.amount_ht:.3f}"


def _build_avoir_tax(parent, credit_note):
    """Build tax section for a credit note."""
    tax_section = etree.SubElement(parent, teif("InvoiceTax"))
    tax_details = etree.SubElement(tax_section, teif("InvoiceTaxDetails"))
    tax = etree.SubElement(tax_details, teif("Tax"))

    etree.SubElement(tax, teif("TaxTypeName"), code="I-1602").text = "TVA"
    rate_details = etree.SubElement(tax, teif("TaxDetails"))
    etree.SubElement(rate_details, teif("TaxRate")).text = f"{credit_note.tva:.2f}"

    # Taxable base (I-177)
    ad_base = etree.SubElement(tax_details, teif("AmountDetails"))
    moa_base = etree.SubElement(
        ad_base, teif("Moa"),
        currencyCodeList="ISO_4217", amountTypeCode="I-177"
    )
    etree.SubElement(moa_base, teif("Amount"), currencyIdentifier="TND").text = f"{credit_note.amount_ht:.3f}"

    # Tax amount (I-178)
    ad_tax = etree.SubElement(tax_details, teif("AmountDetails"))
    moa_tax = etree.SubElement(
        ad_tax, teif("Moa"),
        currencyCodeList="ISO_4217", amountTypeCode="I-178"
    )
    etree.SubElement(moa_tax, teif("Amount"), currencyIdentifier="TND").text = f"{credit_note.calculate_tva_amount():.3f}"


def _build_avoir_totals(parent, credit_note):
    """Build monetary totals for a credit note."""
    moa_section = etree.SubElement(parent, teif("InvoiceMoa"))

    def add_moa(amount_code, amount_value):
        ad = etree.SubElement(moa_section, teif("AmountDetails"))
        moa = etree.SubElement(
            ad, teif("Moa"),
            currencyCodeList="ISO_4217", amountTypeCode=amount_code
        )
        etree.SubElement(moa, teif("Amount"), currencyIdentifier="TND").text = f"{amount_value:.3f}"

    add_moa("I-172", credit_note.amount_ht)        # Total HT
    add_moa("I-176", credit_note.amount_ht)        # Total HT after discount (no discount on avoir)
    add_moa("I-181", credit_note.calculate_tva_amount())  # TVA
    add_moa("I-179", 0)                            # No timbre fiscal on avoir
    add_moa("I-180", credit_note.calculate_total()) # Total TTC


def _build_avoir_body(parent, credit_note, seller):
    """Build the complete credit note body."""
    body = etree.SubElement(parent, teif("InvoiceBody"))

    _build_bgm(body, credit_note, doc_type="I-12", doc_label="Avoir")
    _build_dtm(body, credit_note)

    # Partner section — reuse same structure
    ps = etree.SubElement(body, teif("PartnerSection"))
    _build_partner_details(ps, seller.clientname, seller.mf, seller.adress, "I-62")
    _build_partner_details(ps, credit_note.client.clientname, credit_note.client.mf, credit_note.client.adress, "I-64")

    _build_avoir_lin_section(body, credit_note)
    _build_avoir_totals(body, credit_note)
    _build_avoir_tax(body, credit_note)

    return body


def build_unsigned_teif_avoir(credit_note: CreditNote, seller: Settings) -> bytes:
    """Build unsigned TEIF XML for a credit note (avoir)."""
    if not credit_note.client:
        raise ValueError("Credit note must have a client assigned")
    if not credit_note.uniqueId:
        raise ValueError("Credit note must have a uniqueId")
    if not seller.mf or not credit_note.client.mf:
        raise ValueError("Both seller and client must have MF (Matricule Fiscal)")

    root = etree.Element(
        teif("TEIF"),
        nsmap=NAMESPACE_MAP,
        version=TEIF_VERSION,
        controlingAgency=CONTROLLING_AGENCY,
    )

    _build_invoice_header(root, seller, credit_note.client)
    _build_avoir_body(root, credit_note, seller)

    return etree.tostring(root, encoding='utf-8', xml_declaration=True, pretty_print=True)