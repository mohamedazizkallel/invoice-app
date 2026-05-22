from lxml.etree import QName

# TEIF elements live in the *no-target-namespace* — confirmed by the official
# 1.8.9 XSD (`elementFormDefault="qualified"` with no `targetNamespace`). TTN's
# XPath validators key off this; adding `xmlns="urn:teif"` to the root makes
# `/TEIF/@version` evaluate empty server-side.
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
XADES_NS = "http://uri.etsi.org/01903/v1.3.2#"

# Declared on root so signer/verifier code can reference ds: / xades: prefixes.
NAMESPACE_MAP = {
    "ds": DS_NS,
    "xades": XADES_NS,
}

TEIF_VERSION = "1.8.9"
CONTROLLING_AGENCY = "TTN"

def teif(tag: str) -> str:
    """TEIF elements are unqualified — return a bare tag name."""
    return tag

def ds(tag: str) -> QName:
    return QName(DS_NS, tag)

def xades(tag: str) -> QName:
    return QName(XADES_NS, tag)
