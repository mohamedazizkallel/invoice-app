# Retenue à la source (RAS) — TEIF XML structure

Reference for implementing Tunisian withholding-tax (retenue à la source) in a TEIF
e-invoice, for another app. Based on TTN TEIF schema **1.8.9**
(`1.8.9expl_withoutSig.xsd`), validated codes only.

> Status in this repo: the data model exists (`payment.Retenu`,
> `payment.InvoiceRetenu`), but `gov/teif/builder.py` does **not** yet emit RAS
> into the XML — it only emits TVA (`I-1602`) and timbre fiscal (`I-1601`).
> This doc describes how RAS *should* be encoded so another app can implement it.

## 1. Tax type code

`TaxTypeName/@code` is an enumerated list in the XSD. The relevant members:

| Code     | Meaning            |
|----------|--------------------|
| `I-1601` | Droit de timbre    |
| `I-1602` | TVA                |
| `I-1603` | **Retenue à la source** |

`I-1603` is the *only* code for withholding. The functional sub-type
(acquisitions 1%, loyers 10%, BNC 10%, etc. — see `payment/models.py`
`Retenu.SUBCATEGORY_CHOICES`) is **not** carried in a TEIF code; it only drives
the **rate**. TEIF transports the rate + amounts, not the category.

## 2. Where it goes

RAS is an **invoice-level** tax, not a line-level tax. It lives in `InvoiceTax`
as its own `InvoiceTaxDetails` block (the element is `maxOccurs="unbounded"`, so
timbre, TVA and RAS each get their own block).

Schema path (TEIF elements are unqualified — no namespace prefix):

```
TEIF
└─ InvoiceBody                       (BodyType)
   ├─ Bgm, Dtm, PartnerSection, LinSection
   ├─ InvoiceMoa                     (MoaInvoiceType)   ← totals, incl. net-after-RAS
   ├─ InvoiceTax                     (TaxInvoiceType)
   │  └─ InvoiceTaxDetails  (×N)     (TaxDetailsType)
   │     ├─ Tax                      (TaxType)
   │     │  ├─ TaxTypeName code="I-1603"
   │     │  └─ TaxDetails
   │     │     └─ TaxRate
   │     └─ AmountDetails  (×N)      (MoaDetailsType)
   │        └─ Moa amountTypeCode="…"
   │           └─ Amount currencyIdentifier="TND"
   └─ InvoiceAlc (optional)
```

`BodyType` sequence order is fixed: `InvoiceMoa` **before** `InvoiceTax`. Putting
them out of order fails XSD validation.

## 3. RAS InvoiceTaxDetails block

```xml
<InvoiceTax>
  <!-- … timbre fiscal block (I-1601) … -->
  <!-- … TVA block (I-1602) … -->
  <InvoiceTaxDetails>
    <Tax>
      <TaxTypeName code="I-1603">retenue a la source</TaxTypeName>
      <TaxDetails>
        <TaxRate>1.00</TaxRate>            <!-- e.g. 1% acquisitions ≥1000D -->
      </TaxDetails>
    </Tax>
    <AmountDetails>
      <Moa amountTypeCode="I-184" currencyCodeList="ISO_4217">
        <Amount currencyIdentifier="TND">19.228</Amount>   <!-- montant retenu -->
      </Moa>
    </AmountDetails>
  </InvoiceTaxDetails>
</InvoiceTax>
```

`TaxTypeName` text must be non-empty (`NotNullDataStringType_200`). Strip
forbidden chars `% / \ < > & " '` from any text content (TTN rejects them — see
`_sanitize` / `_clean_mf` in `builder.py`).

`TaxRate` is `NotNullDataStringType_5` → max 5 chars, e.g. `1.00`, `10.0`, `2.50`.

## 4. Amounts — amountTypeCode

`amountTypeCode` enum in the XSD spans `I-171` … `I-188`. Confirmed/used in this
codebase:

| Code    | Meaning (verified in repo)                  |
|---------|---------------------------------------------|
| `I-171` | Montant total HT de l'article (line)        |
| `I-172` | Total HT avant remise                       |
| `I-173` | Montant remise globale facture              |
| `I-176` | Total HT après remise                       |
| `I-177` | Montant base taxe                           |
| `I-178` | Montant taxe                                |
| `I-179` | Timbre fiscal                               |
| `I-180` | Total TTC                                   |
| `I-181` | Montant total taxe                          |
| `I-182` | (used in TTN samples, label unconfirmed)    |
| `I-183` | (line amount w/ tax in TTN samples)         |

⚠️ **`I-184`–`I-188` are valid in the XSD but the schema carries no labels.**
The conventional TTN mapping is:
- `I-184` = **montant de la retenue à la source** (the withheld amount)
- a net-à-payer code for the amount the client actually pays (TTC − RAS)

**Before shipping, confirm `I-184` (and the net-payable code) against the
official TTN code-list / "guide d'intégration elfatoora".** XSD validation alone
will pass any `I-18x` code, so a wrong-but-valid code won't be caught by schema
checks — only by TTN server-side business rules.

## 5. Computation

From `payment/models.py`:

```
retenu_amount = base_amount × (rate / 100)
```

- `base_amount` = montant sur lequel la retenue est calculée (usually TTC, or HT
  depending on category — driven by `Retenu.subcategory`).
- Amounts formatted to **3 decimals** (`%.3f`), TND.
- `net_à_payer = total_TTC − retenu_amount` → goes in `InvoiceMoa` under the
  net-payable `amountTypeCode`.

## 6. Rates by category (drives TaxRate)

Source: `payment/populate_retenu.py`. The category is app-side only; only the
**rate** reaches TEIF.

| Category        | Example subtype                       | Rate |
|-----------------|---------------------------------------|------|
| ACQUISITIONS    | PM soumise à l'IS (règle générale)    | 1.0  |
| ACQUISITIONS    | ≥1000 D TTC (PP 2/3 ou PM IS 10%)     | 0.5  |
| ACQUISITIONS    | ≥1000 D TTC (IS 15%)                  | 1.5  |
| ACQUISITIONS    | Commission distributeurs (PP)         | 5.0  |
| LOYERS          | Hôtels / résidents                    | 10.0 |
| ACTIVITES_NC    | Honoraires BNC réel / performance     | 10.0 |
| ACTIVITES_NC    | Artistes / créateurs                  | 5.0  |
| ACTIVITES_NC    | BNC forfait d'assiette                | 15.0 |
| CESSIONS        | Fonds de commerce                     | 5.0  |
| CESSIONS        | Immeubles                             | 2.5  |
| DIVIDENDES      | PP résidentes                         | 10.0 |
| CAPITAUX        | Capitaux mobiliers                    | 20.0 |
| JEUX            | Pari / loterie                        | 25.0 |
| JETONS          | Jetons de présence                    | 20.0 |

## 7. Pipeline note

XML is built unsigned → condensed to single line → XAdES-B signed (NGSign,
`Id="SigFrs"` appended last) → delivered to TTN via elfatoora SOAP. RAS amounts
are part of the signed payload, so they must be final **before** signing — no
mutation after `inject_signature`.
