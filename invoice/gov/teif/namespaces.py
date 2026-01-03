from lxml.etree import QName

TEIF_NS = "urn:teif"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
XADES_NS = "http://uri.etsi.org/01903/v1.3.2#"

NAMESPACE_MAP = {
    None: TEIF_NS,
    "ds": DS_NS,
    "xades": XADES_NS,
}

TEIF_VERSION = "1.8.7"
CONTROLLING_AGENCY = "TTN"

def teif(tag: str) -> QName:
    return QName(TEIF_NS, tag)

def ds(tag: str) -> QName:
    return QName(DS_NS, tag)

def xades(tag: str) -> QName:
    return QName(XADES_NS, tag)
