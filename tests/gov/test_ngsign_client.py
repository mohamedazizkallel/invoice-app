import base64
import pytest
import responses
from gov.ngsign.client import (
    create_transaction, check_invoice_status, get_signed_xml,
    get_pds_url, create_org, update_org, refresh_jwt,
    INVOICE_API_BASE, PARTNER_API_BASE, PDS_BASE,
)
from gov.ngsign.exceptions import NGSignAPIError, NGSignAuthError


class TestCreateTransaction:
    @responses.activate
    def test_posts_correct_url(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        responses.post(url, json={'object': {'uuid': 'txn-123', 'invoices': []}}, status=200)

        create_transaction('org-jwt', [{'invoiceFileB64': 'abc'}], 'signer@test.com')

        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @responses.activate
    def test_sends_auth_header(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        responses.post(url, json={'object': {'uuid': 'txn-123', 'invoices': []}}, status=200)

        create_transaction('my-jwt-token', [{}], 'signer@test.com')

        assert responses.calls[0].request.headers['Authorization'] == 'Bearer my-jwt-token'

    @responses.activate
    def test_sends_payload(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        responses.post(url, json={'object': {'uuid': 'txn-123', 'invoices': []}}, status=200)

        payload = [{'invoiceFileB64': 'abc', 'invoiceTIEF': 'def'}]
        create_transaction('jwt', payload, 'signer@test.com')

        import json
        body = json.loads(responses.calls[0].request.body)
        assert body['invoices'] == payload
        assert body['signerEmail'] == 'signer@test.com'

    @responses.activate
    def test_returns_object(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        expected = {'uuid': 'txn-abc', 'invoices': [{'uuid': 'inv-1', 'status': 'CREATED'}]}
        responses.post(url, json={'object': expected}, status=200)

        result = create_transaction('jwt', [{}], 'signer@test.com')
        assert result == expected

    @responses.activate
    def test_raises_on_non_200(self):
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/transaction/create'
        responses.post(url, json={'error': 'bad'}, status=400)

        with pytest.raises(NGSignAPIError, match='create_transaction failed'):
            create_transaction('jwt', [{}], 'signer@test.com')


class TestCheckInvoiceStatus:
    @responses.activate
    def test_correct_url(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/check/{uuid}'
        responses.post(url, json={'object': {'status': 'CREATED'}}, status=200)

        check_invoice_status('jwt', uuid)
        assert responses.calls[0].request.url == url

    @responses.activate
    def test_returns_object(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/check/{uuid}'
        expected = {'status': 'SIGNED', 'ttnReference': 'TTN-001'}
        responses.post(url, json={'object': expected}, status=200)

        result = check_invoice_status('jwt', uuid)
        assert result == expected

    @responses.activate
    def test_raises_on_non_200(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/check/{uuid}'
        responses.post(url, status=500)

        with pytest.raises(NGSignAPIError, match='check_invoice_status failed'):
            check_invoice_status('jwt', uuid)


class TestGetSignedXml:
    @responses.activate
    def test_decodes_base64(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/xml/{uuid}'
        xml_content = b'<TEIF>signed</TEIF>'
        b64 = base64.b64encode(xml_content).decode()
        responses.get(url, json={'object': b64}, status=200)

        result = get_signed_xml('jwt', uuid)
        assert result == xml_content

    @responses.activate
    def test_raises_on_non_200(self):
        uuid = 'inv-uuid-123'
        url = f'{INVOICE_API_BASE}/protected/invoice/xml/xml/{uuid}'
        responses.get(url, status=404)

        with pytest.raises(NGSignAPIError, match='get_signed_xml failed'):
            get_signed_xml('jwt', uuid)


class TestGetPdsUrl:
    def test_format(self):
        result = get_pds_url('txn-abc-123')
        assert result == f'{PDS_BASE}/txn-abc-123'


class TestCreateOrg:
    @responses.activate
    def test_correct_url_and_payload(self):
        url = f'{PARTNER_API_BASE}/protected/user/partner/create'
        responses.post(url, json={'object': {'uuid': 'org-1', 'jwt': 'new-jwt'}}, status=200)

        result = create_org('partner-jwt', 'My Org', '123 Street', 'org@test.com')

        import json
        body = json.loads(responses.calls[0].request.body)
        assert body['name'] == 'My Org'
        assert body['street'] == '123 Street'
        assert body['country'] == 'TN'
        assert body['partnerUser']['email'] == 'org@test.com'
        assert result == {'uuid': 'org-1', 'jwt': 'new-jwt'}

    @responses.activate
    def test_raises_on_non_200(self):
        url = f'{PARTNER_API_BASE}/protected/user/partner/create'
        responses.post(url, status=500)

        with pytest.raises(NGSignAPIError, match='create_org failed'):
            create_org('partner-jwt', 'Org', 'Addr', 'e@t.com')


class TestUpdateOrg:
    @responses.activate
    def test_correct_url_and_payload(self):
        url = f'{PARTNER_API_BASE}/protected/user/partner/update'
        responses.post(url, json={'object': {'uuid': 'org-1', 'jwt': 'upd-jwt'}}, status=200)

        result = update_org('partner-jwt', 'old-jwt', 'Updated Org', '456 Ave', 'u@t.com')

        import json
        body = json.loads(responses.calls[0].request.body)
        assert body['jwt'] == 'old-jwt'
        assert body['name'] == 'Updated Org'
        assert result == {'uuid': 'org-1', 'jwt': 'upd-jwt'}


class TestRefreshJwt:
    @responses.activate
    def test_returns_new_jwt(self):
        uuid = 'org-uuid-1'
        url = f'{PARTNER_API_BASE}/protected/user/partner/refresh/{uuid}'
        responses.post(url, json={'object': {'jwt': 'refreshed-jwt'}}, status=200)

        result = refresh_jwt('partner-jwt', uuid)
        assert result == 'refreshed-jwt'

    @responses.activate
    def test_raises_on_non_200(self):
        uuid = 'org-uuid-1'
        url = f'{PARTNER_API_BASE}/protected/user/partner/refresh/{uuid}'
        responses.post(url, status=401)

        with pytest.raises(NGSignAuthError, match='refresh_jwt failed'):
            refresh_jwt('partner-jwt', uuid)
