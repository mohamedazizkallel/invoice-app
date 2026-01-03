from lxml import etree

def freeze_unsigned_xml(xml_bytes: bytes) -> bytes:
    """
    Final gate before signing.
    This must be the exact payload the user signs.
    """
    if not isinstance(xml_bytes, (bytes, bytearray)):
        raise TypeError("XML must be bytes")

    return bytes(xml_bytes)

def load_signature_block(signature_xml: bytes) -> etree._Element:
    try:
        sig = etree.fromstring(signature_xml)
    except Exception:
        raise ValueError("Invalid signature XML")

    if not sig.tag.endswith("Signature"):
        raise ValueError("Root element must be ds:Signature")

    return sig


def inject_signature(unsigned_xml: bytes, signature_node: etree._Element) -> bytes:
    root = etree.fromstring(unsigned_xml)

    if root.xpath(".//*[local-name()='Signature']"):
        raise ValueError("XML already contains a signature")

    root.append(signature_node)

    # CRITICAL: Use c14n for guaranteed single-line format
    return etree.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
        method='c14n'  # Not pretty_print=False
    )


def serialize_signed_teif(unsigned_xml: bytes, signature_xml: bytes) -> bytes:
    frozen = freeze_unsigned_xml(unsigned_xml)
    signature = load_signature_block(signature_xml)
    return inject_signature(frozen, signature)




