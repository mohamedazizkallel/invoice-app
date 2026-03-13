# NGSign Creation Invoice API

Source: https://www.ng-sign.com/api-ngsign-elfatoora/creation-invoice-api/#/
OpenAPI spec: ./openapi.json
Build: 04/02/2026 09:14
Version: 2.37 / OAS 3.0

## Overview

Génération de Factures XML + Signature + Transmission TTN.
This API generates invoices in XML (TEIF) format, signs them (manually or via electronic seal/SEAL), and transmits them to TTN (Tunisie TradeNet).

## Base URL (Sandbox)

`https://sandbox.ng-sign.com/server`

## Authentication

All calls require an API token (Bearer JWT) associated with the invoice signer's account or a user in their organization.

- If YOU are the signer → use your own API token (NGSIGNE_API)
- If a CLIENT is the signer → use the client's JWT (obtained via Partner API `/create`)

## Workflow

1. Prepare invoice data (supplier, client, items, taxes)
2. Create Transaction via one of the endpoints
3. Sign:
   - Seal: automatic, returns transaction immediately
   - Manual: returns PDS URL for redirect
4. NGSign transmits to TTN
5. Track via `/check` or receive via callbacks

---

## Creation Endpoints

| Use Case | Endpoint | Returns |
|---|---|---|
| Simple (manual sign) | `POST /protected/invoice/transaction` | PDS URL (string) |
| Simple V2 (manual sign) | `POST /protected/invoice/v2/transaction` | Transaction object |
| Advanced (3rd-party signer, CC) | `POST /protected/invoice/transaction/advanced` | PDS URL (string) |
| Advanced V2 | `POST /protected/invoice/v2/transaction/advanced` | Transaction object |
| Seal (auto-sign) | `POST /protected/invoice/transaction/seal` | Transaction object |
| Seal V2 (auto-sign) | `POST /protected/invoice/v2/transaction/seal` | Transaction object |

---

## Request Body (shared structure for all endpoints)

```json
[  // array of invoices (for simple/v2/transaction); wrapped in {"invoices": [...]} for advanced/seal
  {
    "invoiceFileB64": "string",       // optional: base64-encoded PDF invoice
    "type": "I_11",                   // document type code
    "configuration": {
      "qrPositionX": 0,
      "qrPositionY": 0,
      "qrPositionP": 0,
      "allPages": true
    },
    "invoiceTIEF": {                  // REQUIRED: structured invoice data
      "supplierIdentifier": "string", // seller MF (matricule fiscal)
      "supplierDetails": {
        "partnerIdentifier": "string",
        "partnerName": "string",
        "address": {
          "description": "string",
          "street": "string",
          "cityName": "string",
          "postalCode": "string",
          "country": "string"         // e.g. "TN"
        }
      },
      "clientIdentifier": "string",   // REQUIRED: client MF
      "clientDetails": {              // REQUIRED
        "partnerIdentifier": "string",
        "partnerName": "string",
        "address": {
          "description": "string",
          "street": "string",
          "cityName": "string",
          "postalCode": "string",
          "country": "string"
        }
      },
      "documentIdentifier": "string", // REQUIRED: invoice number (e.g. "001-2025")
      "documentReferences": [         // optional: references to other docs
        {"value": "string", "refID": "string"}
      ],
      "documentType": "I-11",         // invoice type: I-11 = standard invoice
      "invoiceDate": "2026-03-13T15:28:39.105Z",
      "items": [                      // REQUIRED: line items
        {
          "name": "string",           // REQUIRED
          "code": "string",           // REQUIRED
          "unit": "UNIT",             // e.g. "C62" for unit
          "quantity": 0,              // REQUIRED
          "tvaRate": 0,               // TVA %
          "unitPrice": 0,             // REQUIRED
          "totalPrice": 0,            // REQUIRED
          "taxes": [
            {
              "code": "string",       // e.g. "I-1602" for TVA
              "taxRate": "string",
              "amount": 0,
              "amountBase": 0
            }
          ]
        }
      ],
      "invoiceTotalWithoutTax": 0,
      "invoiceTotalWithTax": 0,
      "invoiceTotalTax": 0,
      "currencyIdentifier": "TND",
      "taxes": [
        {
          "code": "string",
          "taxRate": "string",
          "amount": 0,
          "amountBase": 0
        }
      ],
      "paymentDetails": [             // optional
        {
          "pyt": {"paymentTearmsTypeCode": "string"},
          "amount": 0,
          "pytPai": {"paiConditionCode": "string", "paiMeansCode": "string"},
          "pytFii": {
            "accountHolder": {"accountNumber": "string"},
            "institutionIdentification": {"nameCode": "string"}
          }
        }
      ]
    },
    "clientEmail": "string",          // optional
    "callbackUrl": {
      "successUrl": "string",
      "failureUrl": "string"
    }
  }
]
```

For **Advanced / Seal** endpoints, wrap invoices array and add:
```json
{
  "invoices": [...],
  "signerEmail": "string",
  "passphrase": "string",
  "notifyOwner": true,
  "ccEmail": "string",
  "redirectedTo": "string",
  "transactionLang": "fr",
  "sendToSigner": true
}
```

---

## Response Schemas

### Transaction Object (V2 / Seal)
```json
{
  "object": {
    "uuid": "string",
    "status": "string",
    "creationDate": "datetime",
    "invoices": [
      {
        "uuid": "string",
        "status": "string",
        "invoiceNumber": "string",
        "ttnReference": "string"
      }
    ]
  },
  "message": "string"
}
```

### Simple (V1) - returns PDS URL
```json
{
  "object": "string",   // PDS URL to redirect signer to
  "message": "string"
}
```

---

## Management Endpoints

| Function | Endpoint | Notes |
|---|---|---|
| Cancel transaction | `POST /protected/invoice/transaction/cancel/{uuid}` | Cancels all non-transmitted invoices |
| Cancel invoice | `POST /protected/invoice/cancel/{uuid}` | Must be in CREATED/SIGNED/TTN_REJECTED status |
| Check TTN status | `POST /protected/invoice/check/{uuid}` | Forces sync with TTN |
| List statuses | `GET /protected/invoice/status` | All possible statuses — good for connectivity test |
| Download PDF | `GET /protected/invoice/pdf/{uuid}` | Returns base64 PDF |
| Download XML | `GET /protected/invoice/xml/{uuid}` | Returns base64 TEIF XML |

---

## Signing Page (PDS) URL

After creating a manual-sign transaction:
```
https://sandbox.ng-sign.com/pds/#/invoice/{transaction_uuid}
```

---

## Key Notes

- `invoiceTIEF` replaces raw XML — the API builds the TEIF XML internally from this JSON
- `invoiceFileB64` is the optional PDF attachment
- The project already has a TEIF XML builder in `gov/teif/builder.py` — the JSON fields map 1:1 with what the builder produces
- `GET /protected/invoice/status` is the cheapest connectivity test (no body required)
- Document types: `I-11` = standard invoice, `I-12` = credit note, `I-15` = other
