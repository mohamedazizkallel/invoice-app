from lxml import etree

def validate_partners(invoice):
    seller = invoice.seller
    buyer = invoice.client

    if not seller:
        raise ValueError("Invoice has no seller")

    if not seller.matricule_fiscal or len(seller.matricule_fiscal) != 13:
        raise ValueError("Invalid seller Matricule Fiscal")

    if not seller.legal_name:
        raise ValueError("Seller legal name is required")

    if not buyer:
        raise ValueError("Invoice has no buyer")

    if not buyer.name:
        raise ValueError("Buyer name is required")

    if not buyer.identifier:
        raise ValueError("Buyer identifier is required")

def validate_lines(invoice):
    lines = invoice.invoiceservice_set.all()

    if not lines.exists():
        raise ValueError("Invoice must contain at least one line")

    for idx, line in enumerate(lines, start=1):
        if not line.description:
            raise ValueError(f"Line {idx}: description missing")

        if line.quantity <= 0:
            raise ValueError(f"Line {idx}: quantity must be > 0")

        if line.unit_price < 0:
            raise ValueError(f"Line {idx}: unit price invalid")

        if line.line_total < 0:
            raise ValueError(f"Line {idx}: line total invalid")

        if line.tax_rate is None:
            raise ValueError(f"Line {idx}: tax rate missing")

def validate_totals(invoice):
    lines = invoice.invoiceservice_set.all()

    computed_ht = sum(l.line_total for l in lines)

    if computed_ht != invoice.total_htva:
        raise ValueError("Total HTVA does not match sum of lines")

    if invoice.total_ttc < invoice.total_htva:
        raise ValueError("Total TTC cannot be less than HTVA")

def validate_invoice_for_teif(invoice):
    validate_partners(invoice)
    validate_lines(invoice)
    validate_totals(invoice)



def validate_unsigned_xml(xml_bytes: bytes):
    print(xml_bytes[:80])

    if not xml_bytes:
        raise ValueError("Empty XML")

    if xml_bytes.startswith(b"\xef\xbb\xbf"):
        raise ValueError("XML must not contain BOM")

    if b"\n" in xml_bytes or b"\r" in xml_bytes:
        raise ValueError("XML must be single-line before signing")

    try:
        root = etree.fromstring(xml_bytes)
    except Exception:
        raise ValueError("XML is not well-formed")

    if root.tag.endswith("Signature"):
        raise ValueError("Unsigned XML must not contain ds:Signature")
