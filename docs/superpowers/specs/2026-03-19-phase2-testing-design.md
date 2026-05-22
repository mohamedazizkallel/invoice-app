# Phase 2 Testing Strategy Design — Broad App Coverage

**Date:** 2026-03-19
**Scope:** Full sales app, payment system, and utilities — everything outside NGSign

---

## 1. Test Organization

Restructure `tests/` to separate Phase 1 (NGSign) from Phase 2:

```
tests/
├── conftest.py              (shared fixtures — existing, expanded)
├── factories.py             (shared factories — existing, expanded)
├── ngsign/                  (Phase 1 — move existing files)
│   ├── __init__.py
│   ├── test_ngsign_client.py
│   ├── test_ngsign_service.py
│   ├── test_ngsign_serializer.py
│   ├── test_teif_builder.py
│   ├── test_async_submission.py
│   └── test_notification_api.py
├── sales/                   (Phase 2 — new)
│   ├── __init__.py
│   ├── test_models.py       (move + expand existing test_models.py)
│   ├── test_invoice_views.py
│   ├── test_credit_note_views.py
│   ├── test_client_views.py
│   ├── test_supplier_views.py
│   ├── test_purchase_views.py
│   ├── test_devis_views.py
│   ├── test_bon_livraison_views.py
│   ├── test_service_views.py
│   ├── test_settings_views.py
│   └── test_utilities.py
└── payment/                 (Phase 2 — new)
    ├── __init__.py
    ├── test_retenu_models.py
    └── test_payment_views.py
```

Phase 1 imports in conftest/factories remain unchanged. New Phase 2 factories are appended.

---

## 2. New Factories

Add to existing `tests/factories.py`:

### SupplierFactory
- `name`: `factory.Sequence(lambda n: f'Supplier {n}')`
- `mf`: `factory.Sequence(lambda n: f'MF-S-{n:04d}')`
- `adress`: `'123 Supplier St'`
- `status`: `'PM'`

### SupplyFactory
- `name`: `factory.Sequence(lambda n: f'Supply {n}')`
- `category`: `'raw_material'`
- `unit`: `'pièce'`
- `unit_price`: `Decimal('10.000')`
- `stock_quantity`: `Decimal('100.000')`
- `min_stock`: `Decimal('10.000')`
- `apply_fodec`: `False`

### PurchaseFactory
- `supplier`: `SubFactory(SupplierFactory)`
- `status`: `'DRAFT'`
- `tva`: `Decimal('19.00')`
- `discount`: `Decimal('0.00')`
- `timbre_fiscal`: `Decimal('1.000')`

### PurchaseLineFactory
- `purchase`: `SubFactory(PurchaseFactory)`
- `supply`: `SubFactory(SupplyFactory)`
- `quantity`: `Decimal('5.000')`
- `unit_price`: `Decimal('10.000')`
- `has_fodec`: `False`

### ClientTransactionFactory
- `client`: `SubFactory(ClientFactory)`
- `transaction_type`: `'DEBIT'`
- `source`: `'MANUAL'`
- `amount`: `Decimal('100.000')`

### SupplierTransactionFactory
- `supplier`: `SubFactory(SupplierFactory)`
- `transaction_type`: `'CREDIT'`
- `source`: `'MANUAL'`
- `amount`: `Decimal('100.000')`

### DevisFactory
- `client`: `SubFactory(ClientFactory)`
- `title`: `factory.Sequence(lambda n: f'Devis {n}')`
- `tva`: `Decimal('19.00')`
- `timbre_fiscal`: `Decimal('1.000')`
- `discount`: `Decimal('0.00')`
- `status`: `'PENDING'`

### BonLivraisonFactory
- `client`: `SubFactory(ClientFactory)`
- `status`: `'DRAFT'`
- `tva`: `Decimal('19.00')`

### BonLivraisonLineFactory
- `bon`: `SubFactory(BonLivraisonFactory)`
- `description`: `factory.Sequence(lambda n: f'Line item {n}')`
- `amount`: `Decimal('50.000')`

### RetenuFactory
- `category`: `'ACQUISITIONS'`
- `subcategory`: `factory.Sequence(lambda n: f'ACQ_TEST_{n}')`
  *(Note: subcategory is unique — each test must use unique values)*
- `rate`: `Decimal('1.00')`
- `is_active`: `True`

### InvoiceRetenuFactory
- `invoice`: `SubFactory(InvoiceFactory)`
- `retenu_type`: `SubFactory(RetenuFactory)`
- `base_amount`: `Decimal('1000.000')`
- `retenu_rate`: `factory.LazyAttribute(lambda o: o.retenu_type.rate)`
- `retenu_amount`: `factory.LazyAttribute(lambda o: (o.base_amount * o.retenu_rate) / Decimal('100'))`

### PurchaseRetenuFactory
- `purchase`: `SubFactory(PurchaseFactory)`
- `retenu_type`: `SubFactory(RetenuFactory)`
- `base_amount`: `Decimal('1000.000')`
- `retenu_rate`: `factory.LazyAttribute(lambda o: o.retenu_type.rate)`
- `retenu_amount`: `factory.LazyAttribute(lambda o: (o.base_amount * o.retenu_rate) / Decimal('100'))`

### DevisServiceFactory
InvoiceService linked to a Devis instead of an Invoice. Needed for Devis calculation tests.
- `devis`: `SubFactory(DevisFactory)`
- `invoice`: `None`
- `service`: `SubFactory(ServiceFactory)`
- `unit_price`: `Decimal('100.000')`
- `has_fodec`: `False`

---

## 3. Shared Conftest Additions

### `logged_in_client` fixture
Use existing `logged_in_client` fixture from `conftest.py` (already creates an authenticated Django test client).
All view tests use `logged_in_client` for auth.

### Cache clearing
```python
@pytest.fixture(autouse=True)
def clear_cache():
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
```

---

## 4. Test Cases — Sales Models (`tests/sales/test_models.py`)

Expand existing Phase 1 model tests. Move existing file, add new tests.

### Client model (4 tests)
| Test | What it verifies |
|------|-----------------|
| `test_client_save_generates_unique_id_and_slug` | save() auto-generates uniqueId and slug |
| `test_client_get_balance_net_debit` | get_balance() = DEBIT - CREDIT |
| `test_client_get_balance_no_transactions` | get_balance() returns 0 when no transactions |
| `test_client_mf_cache_invalidation` | save()/delete() invalidates MF cache |

### Supplier model (3 tests)
| Test | What it verifies |
|------|-----------------|
| `test_supplier_save_generates_unique_id_and_slug` | save() auto-generates uniqueId and slug |
| `test_supplier_get_balance_net_credit` | get_balance() = CREDIT - DEBIT (we owe supplier) |
| `test_supplier_mf_cache_invalidation` | save()/delete() invalidates MF cache |

### Supply model (2 tests)
| Test | What it verifies |
|------|-----------------|
| `test_supply_is_low_stock_true` | is_low_stock when stock_quantity <= min_stock |
| `test_supply_is_low_stock_false` | not is_low_stock when stock_quantity > min_stock |

### Purchase model (7 tests)
| Test | What it verifies |
|------|-----------------|
| `test_purchase_calculate_subtotal` | Sum of all PurchaseLine totals |
| `test_purchase_calculate_discount_amount` | Discount % applied to subtotal |
| `test_purchase_calculate_total_fodec` | Sum of line FODEC amounts |
| `test_purchase_calculate_tva_amount` | TVA on (subtotal_after_discount + FODEC) |
| `test_purchase_calculate_total` | Full total including timbre fiscal |
| `test_purchase_get_net_amount` | Total minus retenues |
| `test_purchase_uniqueId_sequential` | save() generates "001-2026" format IDs |

### PurchaseLine model (2 tests)
| Test | What it verifies |
|------|-----------------|
| `test_purchase_line_get_line_total` | quantity × unit_price |
| `test_purchase_line_get_fodec_amount` | 1% when has_fodec=True, 0 when False |

### Invoice model (15 tests — expanding Phase 1)
| Test | What it verifies |
|------|-----------------|
| `test_invoice_calculate_service_subtotal` | Sum of InvoiceService.get_line_ht() |
| `test_invoice_calculate_total_fodec` | Sum of service FODEC amounts |
| `test_invoice_calculate_discount_amount` | Discount % on subtotal |
| `test_invoice_calculate_tva_amount` | TVA on (subtotal_after_discount + FODEC) |
| `test_invoice_calculate_total_tva` | subtotal_after_discount + FODEC + TVA (no timbre) |
| `test_invoice_calculate_total` | Full TTC including timbre |
| `test_invoice_get_total_retenue` | Aggregate of InvoiceRetenu amounts |
| `test_invoice_get_net_amount` | Total minus retenues |
| `test_invoice_get_auto_retenu_above_threshold` | Auto-retenu when total > 1000D and no manual retenues |
| `test_invoice_get_auto_retenu_below_threshold` | Returns 0 when total <= 1000D |
| `test_invoice_get_auto_retenu_manual_exists` | Returns 0 when manual retenu already applied |
| `test_invoice_get_credit_notes_total` | Sum of linked CreditNote totals |
| `test_invoice_has_retenue` | Returns True with retenues, False without |
| `test_invoice_uniqueId_sequential` | save() generates "FV-001-2026" format |
| `test_invoice_save_auto_populates_from_settings` | tva/timbre_fiscal from Settings when null |

### InvoiceService model (4 tests — Phase 1 has some, expand)
| Test | What it verifies |
|------|-----------------|
| `test_invoice_service_get_line_ht_flat` | unit_price for flat billing |
| `test_invoice_service_get_line_ht_hour` | unit_price × hours_used |
| `test_invoice_service_get_line_ht_day` | unit_price × days_used |
| `test_invoice_service_get_line_ht_unit` | unit_price × units_used |

### CreditNote model (3 tests)
| Test | What it verifies |
|------|-----------------|
| `test_credit_note_calculate_tva_amount` | amount_ht × tva / 100 |
| `test_credit_note_calculate_total` | amount_ht + TVA |
| `test_credit_note_uniqueId_sequential` | save() generates "AV-001-2026" format |

### BonLivraison model (4 tests)
| Test | What it verifies |
|------|-----------------|
| `test_bon_livraison_calculate_total_ht` | Sum of line amounts |
| `test_bon_livraison_calculate_tva_amount` | total_ht × tva / 100 |
| `test_bon_livraison_calculate_total_ttc` | total_ht + tva_amount |
| `test_bon_livraison_uniqueId_sequential` | save() generates "BL-001-2026" format |

### Devis model (8 tests)
| Test | What it verifies |
|------|-----------------|
| `test_devis_calculate_service_subtotal` | Sum of devis_services line HT |
| `test_devis_calculate_total_fodec` | Sum of devis_services FODEC amounts |
| `test_devis_calculate_discount_amount` | Discount applied to (subtotal + FODEC) — differs from Invoice |
| `test_devis_calculate_tva_amount` | TVA on (subtotal + FODEC - discount) |
| `test_devis_calculate_total` | subtotal + FODEC - discount + TVA + timbre |
| `test_devis_convert_to_invoice` | Creates Invoice, copies InvoiceService rows, sets ACCEPTED |
| `test_devis_convert_idempotent` | Second call returns same invoice |
| `test_devis_uniqueId_sequential` | save() generates "DV-001-2026" format |

### Service model (4 tests)
| Test | What it verifies |
|------|-----------------|
| `test_service_total_price_flat` | Returns price directly |
| `test_service_total_price_day` | price × duration_days |
| `test_service_total_price_hour` | price × duration_hours |
| `test_service_total_price_unit` | Falls through to price (no multiplier) |

### Settings model (3 tests)
| Test | What it verifies |
|------|-----------------|
| `test_settings_get_cached` | Returns cached singleton |
| `test_settings_cache_invalidation_on_save` | save() invalidates cache |
| `test_settings_save_auto_generates_fields` | uniqueId, slug, timestamps |

**Total model tests: ~50**

---

## 5. Test Cases — Sales Views

### `tests/sales/test_invoice_views.py` (10 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_invoice_create_success` | `invoice_create` | Creates Invoice, InvoiceService, DEBIT ledger entry |
| `test_invoice_create_no_client` | `invoice_create` | Returns error when no client |
| `test_invoice_create_no_services` | `invoice_create` | Returns error when no services |
| `test_invoice_create_ledger_debit` | `invoice_create` | ClientTransaction DEBIT = invoice total |
| `test_invoice_edit_updates_fields` | `invoice_edit` | Updates invoice fields |
| `test_invoice_delete_removes_ledger` | `invoice_delete` | Deletes all related ledger entries |
| `test_invoice_delete_post_only` | `invoice_delete` | GET redirects without deleting |
| `test_invoice_list_requires_login` | `invoices_list` | Unauthenticated → redirect to login |
| `test_invoice_list_search` | `invoices_list` | Search by title/client filters results |
| `test_invoice_detail_renders` | `invoice_detail` | Returns 200 with correct context |

### `tests/sales/test_credit_note_views.py` (6 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_avoir_create_success` | `avoir_create` | Creates CreditNote + CREDIT ledger entry |
| `test_avoir_create_no_description` | `avoir_create` | Error when description missing |
| `test_avoir_create_no_amount` | `avoir_create` | Error when amount_ht missing |
| `test_avoir_create_with_linked_invoice` | `avoir_create` | Links to invoice when invoice_id provided |
| `test_avoir_delete_post_only` | `avoir_delete` | GET redirects |
| `test_avoir_detail_renders` | `avoir_detail` | Returns 200 |

### `tests/sales/test_client_views.py` (10 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_clients_list_renders` | `clients` | Returns 200 with client list |
| `test_clients_list_search` | `clients` | Filters by clientname |
| `test_edit_client_updates_fields` | `edit_client` | POST updates client fields |
| `test_delete_client` | `delete_client` | Removes client |
| `test_client_add_transaction_manual` | `client_add_transaction` | Creates manual DEBIT/CREDIT entry |
| `test_client_add_credit_updates_invoice_paid` | `client_add_transaction` | CREDIT linked to invoice increases amount_paid |
| `test_client_add_credit_marks_paid` | `client_add_transaction` | amount_paid >= total → status='PAID' |
| `test_client_delete_transaction` | `client_delete_transaction` | POST deletes, GET returns 405 |
| `test_client_unpaid_invoices_json` | `client_unpaid_invoices` | Returns JSON with unpaid invoices + remaining balance |
| `test_mf_map_returns_json` | `mf_map` | Returns cached MF→client mapping |

### `tests/sales/test_supplier_views.py` (5 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_suppliers_list_renders` | `suppliers` | Returns 200 |
| `test_edit_supplier_updates_fields` | `edit_supplier` | POST updates supplier |
| `test_delete_supplier` | `delete_supplier` | Removes supplier |
| `test_supplier_add_transaction` | `supplier_add_transaction` | Creates manual ledger entry |
| `test_supplier_transactions_json` | `supplier_transactions` | Returns ledger JSON |

### `tests/sales/test_purchase_views.py` (9 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_purchase_create_success` | `purchase_create` | Creates Purchase + PurchaseLines |
| `test_purchase_confirm_increments_stock` | `purchase_confirm` | Increases supply.stock_quantity per line |
| `test_purchase_confirm_creates_supplier_credit` | `purchase_confirm` | SupplierTransaction CREDIT = purchase total |
| `test_purchase_confirm_sets_received` | `purchase_confirm` | status → RECEIVED |
| `test_purchase_confirm_already_paid` | `purchase_confirm` | Rejects if status = PAID |
| `test_purchase_payment_creates_debit` | `process_purchase_payment` | SupplierTransaction DEBIT = purchase total |
| `test_purchase_payment_sets_paid` | `process_purchase_payment` | status → PAID |
| `test_purchase_payment_already_paid` | `process_purchase_payment` | Rejects if already PAID |
| `test_purchase_delete` | `purchase_delete` | Removes purchase |

### `tests/sales/test_devis_views.py` (5 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_devis_create_success` | `devis_create` | Creates Devis + InvoiceService rows (linked to devis, not invoice) |
| `test_devis_update_fields` | `devis_update` | Updates devis + rebuilds services |
| `test_devis_convert_creates_invoice` | `devis_convert` | Calls convert_to_invoice(), redirects to invoice |
| `test_devis_convert_already_converted` | `devis_convert` | Returns info message, redirects to existing invoice |
| `test_devis_delete` | `devis_delete` | Removes devis |

### `tests/sales/test_bon_livraison_views.py` (4 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_bon_create_success` | `bon_livraison_create` | Creates BonLivraison + lines |
| `test_bon_detail_renders` | `bon_livraison_detail` | Returns 200 with calculations |
| `test_bon_edit_rebuilds_lines` | `bon_livraison_edit` | Updates lines |
| `test_bon_delete` | `bon_livraison_delete` | Removes bon |

### `tests/sales/test_service_views.py` (4 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_service_list_renders` | `service_view` | Returns 200 |
| `test_service_list_search` | `service_view` | Filters by title/description |
| `test_add_service` | `add_service` | Creates service via form |
| `test_delete_service` | `delete_service` | Removes service |

### `tests/sales/test_settings_views.py` (3 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_settings_view_renders` | `settings_view` | Returns 200 with form |
| `test_settings_save_updates_fields` | `settings_view` | POST saves company info |
| `test_company_logo_serves_base64` | `company_logo` | Returns logo image response |

**Total view tests: ~56**

---

## 6. Test Cases — Payment (`tests/payment/`)

### `tests/payment/test_retenu_models.py` (6 tests)

| Test | What it verifies |
|------|-----------------|
| `test_invoice_retenu_auto_calculates_amount` | save() computes retenu_amount = base × rate / 100 |
| `test_invoice_retenu_auto_populates_rate` | save() copies rate from retenu_type when retenu_rate is empty |
| `test_invoice_retenu_calculate_amount_method` | calculate_amount() returns correct value |
| `test_purchase_retenu_auto_calculates` | Same auto-calc for purchase retenues |
| `test_purchase_retenu_auto_populates_rate` | Same rate copy for purchase retenues |
| `test_retenu_str_display` | __str__ returns subcategory display |

### `tests/payment/test_payment_views.py` (9 tests)

| Test | View | What it verifies |
|------|------|-----------------|
| `test_process_payment_partial` | `process_payment` | Adds to amount_paid, creates CREDIT ledger, remains CURRENT |
| `test_process_payment_full` | `process_payment` | Sets status=PAID when amount_paid >= effective_total |
| `test_process_payment_clamps_to_remaining` | `process_payment` | Clamps payment to remaining balance |
| `test_process_payment_zero_amount` | `process_payment` | Rejects 0 or negative payment |
| `test_process_payment_with_credit_notes` | `process_payment` | Effective total deducts credit note totals |
| `test_process_payment_with_auto_retenu` | `process_payment` | Effective total deducts auto-retenu |
| `test_process_payment_creates_ledger_credit` | `process_payment` | ClientTransaction CREDIT with INVOICE_PAID source |
| `test_get_retenu_rate_json` | `get_retenu_rate` | Returns JSON with rate, category, subcategory |
| `test_calculate_retenu_preview` | `calculate_retenu_preview` | Returns preview calculation without saving |

**Total payment tests: ~15**

---

## 7. Test Cases — Utilities (`tests/sales/test_utilities.py`)

### `num2words_tnd_fr` (8 tests)

| Test | Input | Expected output |
|------|-------|----------------|
| `test_zero` | `Decimal('0')` | `'zéro dinar'` → Actually `'zéro dinars'` (num2words returns "zéro", dinars since 0 ≠ 1) |
| `test_one_dinar` | `Decimal('1.000')` | `'un dinar'` |
| `test_whole_dinars` | `Decimal('1234.000')` | `'mille deux cent trente-quatre dinars'` |
| `test_millimes_only` | `Decimal('0.500')` | `'zéro dinars et cinq cents millimes'` |
| `test_one_millime` | `Decimal('0.001')` | `'zéro dinars et un millime'` |
| `test_mixed` | `Decimal('42.750')` | `'quarante-deux dinars et sept cent cinquante millimes'` |
| `test_rounding` | `Decimal('1.9999')` | Rounds to `2.000` → `'deux dinars'` |
| `test_large_number` | `Decimal('999999.999')` | Contains `'neuf cent quatre-vingt-dix-neuf mille'` ... |

**Total utility tests: 8**

---

## 8. Mocking Strategy

- **Settings.save()**: Mock `sales.models._sync_ngsign_org` in `seller` fixture to prevent real API calls
- **Cache**: `clear_cache` autouse fixture clears between tests
- **Auth**: `client.force_login(user)` via `logged_in_client` fixture
- **File uploads**: `SimpleUploadedFile` for logo tests
- **No HTTP mocks**: Phase 2 has no external API calls
- **No thread mocks**: No async operations in Phase 2

---

## 9. Coverage

Run with: `pytest --cov=invoice/sales --cov=invoice/payment --cov=invoice/gov -v`

Phase 2 adds coverage for:
- `sales/models.py` (all calculation methods, save(), cache)
- `sales/views.py` (CRUD + workflow views)
- `sales/utilities.py` (num2words_tnd_fr)
- `payment/models.py` (retenu auto-calc)
- `payment/views.py` (payment processing, retenu AJAX)

---

## Summary

| Area | File | Tests |
|------|------|-------|
| Sales Models | `tests/sales/test_models.py` | 59 |
| Invoice Views | `tests/sales/test_invoice_views.py` | 10 |
| Credit Note Views | `tests/sales/test_credit_note_views.py` | 6 |
| Client Views | `tests/sales/test_client_views.py` | 10 |
| Supplier Views | `tests/sales/test_supplier_views.py` | 5 |
| Purchase Views | `tests/sales/test_purchase_views.py` | 9 |
| Devis Views | `tests/sales/test_devis_views.py` | 5 |
| Bon Livraison Views | `tests/sales/test_bon_livraison_views.py` | 4 |
| Service Views | `tests/sales/test_service_views.py` | 4 |
| Settings Views | `tests/sales/test_settings_views.py` | 3 |
| Retenu Models | `tests/payment/test_retenu_models.py` | 6 |
| Payment Views | `tests/payment/test_payment_views.py` | 9 |
| Utilities | `tests/sales/test_utilities.py` | 8 |
| **Total** | | **~138** |
