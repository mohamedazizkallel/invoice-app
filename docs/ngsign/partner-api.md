# NGSign Partner API

Source: https://www.ng-sign.com/api-ngsign-elfatoora/creation-invoice-api/#/

## Overview

NGSign Partner API is dedicated to partners for programmatic management of client accounts and organizations within the NGSign ecosystem. It allows partners to automate organization creation, user management, and e-invoicing configuration for end clients.

## Authentication

All `/protected` endpoints require a JWT Bearer token from the partner's NGSign account:

```
Authorization: Bearer <votre-token-partenaire>
```

The `NGSIGNE_API` env var holds this partner JWT.

---

## Endpoints

### POST /protected/user/partner/create
Create a new client organization and its first admin user.

**Request body (application/json):**
```json
{
  "name": "string",
  "street": "string",
  "cityName": "string",
  "postalCode": "string",
  "country": "string",
  "partnerUser": {
    "email": "string",
    "firstName": "string",
    "lastName": "string",
    "phoneNumber": "string",
    "certificateType": "string"
  },
  "fatooraDetails": {
    "ttnIdentifier": "string",
    "ttnPassword": "string",
    "taxNumber": "string",
    "accountNumber": "string",
    "bankName": "string"
  }
}
```

**Response 200:**
```json
{
  "object": {
    "name": "string",
    "uuid": "string",
    "jwt": "string"    // client-specific JWT for signing invoices on their behalf
  },
  "message": "string",
  "errorCode": 0
}
```
- `400`: Validation error or org already exists
- `401`: Unauthorized (token is not a valid partner token)

---

### POST /protected/user/partner/update
Update an existing organization or user managed by the partner.

**Request body (application/json):**
Same as `/create` plus:
```json
{
  ...
  "jwt": "string"   // JWT of the organization to update
}
```

**Response 200:** Same shape as `/create` response.
- `400`: Validation error or inconsistent data
- `401`: Unauthorized

---

### POST /protected/user/partner/refresh/{uuid}
Regenerate the JWT for a client organization.

**Path parameter:** `uuid` — UUID of the organization

**Response 200:**
```json
{
  "object": {
    "name": "string",
    "uuid": "string",
    "jwt": "string"
  },
  "message": "string",
  "errorCode": 0
}
```
- `400`: Organization not found or not managed by this partner
- `401`: Unauthorized

---

## Key Notes

- After `/create`, store the returned `jwt` per tenant/client — it's used for invoice signing calls on behalf of that client.
- `fatooraDetails` links the NGSign org to TTN (elfatoora) credentials.
- Base URL for sandbox: `https://sandbox.ng-sign.com`
