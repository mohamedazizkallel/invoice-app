# Distributor Invoice App - Feature Design

**Date**: 2026-03-09
**Status**: Approved

## Context

Adapting an existing Django multi-tenant invoice app (Tunisian market - TND, TVA, FODEC, timbre fiscal, retenue) into a distributor invoice app supporting mixed goods (food, beverage, appliances, etc.).

## Key Decisions

- **Target**: Mixed/general distributors
- **Multiple trucks**, each with persistent inventory
- **Owner operates the app** - drivers have no app access
- **Fixed pricing** - no driver discounts
- **Sales channels**: Truck sales (mobile) + Walk-in sales (at warehouse)
- **Unsold goods**: Owner decides per trip (return to warehouse or keep on truck)
- **Sales tracking**: Known clients get invoices, anonymous sales get a single cash summary per trip
- **Basic zones** for trucks (reporting only, no strict routing)
- **Restocking**: Via existing Purchase flow + manual stock adjustments

## Architecture: Hybrid Truck-as-Warehouse

Trucks have persistent inventory, modified only through Trips. This supports keeping goods on truck between trips while maintaining full audit trail.

## New Models

### Truck
| Field | Type | Notes |
|---|---|---|
| name | CharField | "Truck 1", "Blue Fiat" |
| plate_number | CharField | License plate |
| zone | CharField | Area/region (e.g., "Tunis Nord") |
| driver_name | CharField | Text only, no user account |
| is_active | BooleanField | Soft disable |
| uniqueId, slug, date_created, last_updated | — | Standard fields |

### TruckInventory
| Field | Type | Notes |
|---|---|---|
| truck | FK → Truck | |
| service | FK → Service | Product catalog item |
| quantity | DecimalField | Current quantity on truck |
| **Unique together**: (truck, service) | | |

### Trip
| Field | Type | Notes |
|---|---|---|
| truck | FK → Truck | |
| status | CharField | LOADING → IN_PROGRESS → RECONCILING → COMPLETED |
| date_departure | DateTimeField | |
| date_return | DateTimeField | Nullable |
| zone | CharField | Auto-filled from truck, overridable |
| notes | TextField | |
| uniqueId | CharField | e.g., TR-001-2026 |
| slug, date_created, last_updated | — | Standard fields |

### TripLoadLine
| Field | Type | Notes |
|---|---|---|
| trip | FK → Trip | |
| service | FK → Service | |
| quantity_loaded | DecimalField | What was put on truck |

### TripSale
| Field | Type | Notes |
|---|---|---|
| trip | FK → Trip | |
| client | FK → Client | Nullable (null = cash/anonymous) |
| invoice | FK → Invoice | Nullable (generated for known clients) |
| is_cash_sale | BooleanField | |
| notes | TextField | |
| date_created | DateTimeField | |

### TripSaleLine
| Field | Type | Notes |
|---|---|---|
| trip_sale | FK → TripSale | |
| service | FK → Service | |
| quantity | DecimalField | How many sold |
| unit_price | DecimalField | From fixed price list |

### TripReconciliation
| Field | Type | Notes |
|---|---|---|
| trip | OneToOne → Trip | |
| reconciled_by | CharField | Who did the count |
| date_reconciled | DateTimeField | |
| return_to_warehouse | BooleanField | Owner's choice |

### TripReconciliationLine
| Field | Type | Notes |
|---|---|---|
| reconciliation | FK → TripReconciliation | |
| service | FK → Service | |
| quantity_remaining | DecimalField | What's left on truck |
| quantity_sold | DecimalField | Auto-calculated: loaded - remaining |

### StockAdjustment
| Field | Type | Notes |
|---|---|---|
| supply | FK → Supply | |
| quantity_change | DecimalField | Positive (restock) or negative (loss) |
| reason | CharField | MANUAL_RESTOCK, DAMAGE, CORRECTION, RETURN_FROM_TRUCK, OTHER |
| notes | TextField | |
| date_created | DateTimeField | |
| uniqueId | CharField | |

### Modifications to Existing Models

**Invoice** - add `source` field:
- Choices: `STANDARD` (default), `WALK_IN`, `TRUCK_SALE`

**Purchase** - enhance so status `RECEIVED` auto-increments `Supply.stock_quantity`

## Trip Lifecycle

```
LOADING → IN_PROGRESS → RECONCILING → COMPLETED
```

### 1. LOADING
- Owner selects truck, adds products + quantities
- On confirm: Supply.stock_quantity decreases, TruckInventory increases, status → IN_PROGRESS

### 2. IN_PROGRESS
- Truck is on the road
- Owner can optionally pre-register known client sales
- No inventory changes

### 3. RECONCILING
- Truck returns, owner enters remaining quantities per product
- App auto-calculates: quantity_sold = quantity_loaded - quantity_remaining
- Owner records sales:
  - **Known client sales**: picks client + products/quantities → app generates Invoice (source=TRUCK_SALE)
  - **Cash summary**: remaining sold quantity becomes one cash sale entry
- Validation: client sales + cash sales must equal total sold

### 4. COMPLETED
- Owner chooses: return to warehouse or keep on truck
- If return: TruckInventory decreases, Supply.stock_quantity increases
- If keep: TruckInventory stays as-is
- Trip is locked

## Walk-in Sale Flow

1. Owner creates invoice with source=WALK_IN
2. Adds products with quantities
3. On save: Supply.stock_quantity decreases
4. Nullable client for anonymous/cash sales

## Stock Deduction Rules

| Event | Warehouse (Supply) | Truck (TruckInventory) |
|---|---|---|
| Trip loading confirmed | - quantity | + quantity |
| Trip return to warehouse | + quantity | - quantity |
| Trip keep on truck | no change | stays as-is |
| Walk-in sale | - quantity | n/a |
| Purchase received | + quantity | n/a |
| Manual adjustment | +/- quantity | n/a |

## Validation Rules

- Can't load more than warehouse has in stock
- Can't sell more than truck has loaded for that trip
- Client sales + cash sales must equal total sold quantity
- Trip can't complete if reconciliation doesn't add up
- Walk-in sale can't exceed warehouse stock

## Inventory Flow

```
Suppliers → Purchase (RECEIVED) → Warehouse (Supply.stock_quantity)
Manual adjustment → StockAdjustment → Warehouse
Warehouse → Trip loading → Truck inventory
Warehouse → Walk-in sale → Client takes goods
Truck → Trip sale → Client / cash
Truck → Trip reconciliation → Return to warehouse (optional)
```
