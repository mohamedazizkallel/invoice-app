## Goal

Build a multi-tenant (django-tenants) invoice app where each client (tenant) is charged from a **separate credit bucket** at the provider (Option B), managed via **Django admin**, with strong isolation, auditability, and operational controls.

Assumptions:

* “Tokens” = prepaid credits (not identity credentials).
* Integration is API-based.
* django-tenants uses **schemas** with a **public** schema for shared data.

---

## High-level architecture

### Components

1. **Tenant app (per-schema):**

   * Invoices, customers, invoice items, statuses, business logic.
2. **Shared app (public schema):**

   * Tenant registry (already).
   * Provider account mapping + credentials per tenant.
   * Operational logs + audit trail.
3. **Integration service layer (shared code):**

   * Builds requests to provider, handles retries, idempotency, error mapping.
   * Chooses provider bucket/credentials based on current tenant.
4. **Async workers (recommended):**

   * For submission/signing calls, retries, reconciliation, balance sync.

---

## Data model design

### 1) Shared model: Provider account mapping (public schema)

Create an app in `SHARED_APPS` (e.g. `provider_accounts`) with a model like:

**`TenantProviderAccount`**

* `tenant` (FK to your Tenant model; unique)
* `provider` (choice, if multiple providers possible)
* `mode` (choice: `SUBACCOUNT`, `WALLET_ID`, `CLIENT_OWNED_KEYS`)
* `provider_account_id` (string; nullable depending on mode)
* `provider_wallet_id` (string; nullable)
* `api_key_encrypted` (text; nullable)
* `client_id_encrypted`, `client_secret_encrypted` (nullable)
* `status` (ACTIVE / SUSPENDED / PENDING / ERROR)
* `created_at`, `updated_at`
* `last_verified_at` (datetime)
* `last_balance_sync_at` (datetime)
* `balance_cached` (integer/decimal; optional)
* `notes` (text; internal ops notes)

Constraints:

* Unique: `(tenant, provider)`
* Validation:

  * If mode is `SUBACCOUNT`, require `provider_account_id` and one credential method.
  * If mode is `WALLET_ID`, require `provider_wallet_id` plus master auth details (stored elsewhere).
  * If mode is `CLIENT_OWNED_KEYS`, require client-provided keys.

### 2) Shared model: Master/provider config (public schema)

If provider uses one master credential (common for “walletId parameter” designs):

**`ProviderConfig`**

* `provider`
* `base_url`
* `master_api_key_encrypted` (or client credentials)
* `timeout_seconds`, `retry_policy_json`
* `supports_idempotency` (bool)
* `supports_subaccounts` (bool)
* `supports_balance_endpoint` (bool)
* `created_at`, `updated_at`

### 3) Shared model: Integration audit log (public schema)

You need traceability per request.

**`ProviderRequestLog`**

* `tenant` (FK)
* `invoice_id` (string/uuid, reference to tenant schema invoice)
* `operation` (SUBMIT_INVOICE / SIGN / GET_BALANCE / RECONCILE)
* `idempotency_key` (string)
* `request_id` (provider request/correlation id)
* `http_status` (int)
* `result` (SUCCESS/FAIL)
* `error_code` (string)
* `error_message` (short text, sanitized)
* `attempt` (int)
* `duration_ms` (int)
* `created_at`

Do not store raw secrets or full payloads. If you must store payloads, store only sanitized/hashed content.

---

## Credential encryption and secret handling

### Storage

* Encrypt at rest:

  * Preferred: envelope encryption with a KMS/HSM.
  * Acceptable: field-level encryption library with a strong key stored outside repo (env var / secret manager).
* Never store secrets in plaintext.

### Admin display rules

* Secrets should be **write-only** in admin:

  * Show “********” always.
  * Allow setting a new value, not reading the old.
* Track who changed it (audit).

### Logging rules

* Centralized request logging must redact:

  * `Authorization` headers
  * API keys
  * tokens/credits identifiers if sensitive
* Ensure exceptions don’t dump headers.

---

## Django admin plan (how you manage Option B)

### Admin screens you will create

1. **TenantProviderAccount admin**

   * Search by tenant name, provider_account_id, wallet_id
   * Filters: provider, status, mode
   * Fieldsets:

     * Tenant + Provider
     * Mode + Provider IDs
     * Credentials (masked)
     * Status + last verified + balance cached
     * Notes
   * Save hooks:

     * On save, validate required fields by mode.
     * If credential fields changed, mark `last_verified_at = NULL`.

2. **ProviderConfig admin**

   * Only for superusers / ops group.
   * Stores base URL and master credentials (if used).

3. **ProviderRequestLog admin**

   * Read-only (no edits).
   * Filters by tenant, date, operation, result, status code.

### Admin permissions model

Create dedicated groups:

* `IntegrationOps`: can edit TenantProviderAccount, view logs.
* `SecurityAdmin`: can edit ProviderConfig and rotate master creds.
* `SupportReadOnly`: can view account status and balances, cannot edit secrets.

Enforce:

* Only `IntegrationOps` and above can change mappings.
* Only `SecurityAdmin` can change master credentials.

### Admin actions (recommended)

Add admin actions/buttons on `TenantProviderAccount`:

* **Verify credentials / connectivity**

  * Calls a cheap provider endpoint (e.g., “get balance”).
  * Writes result to `last_verified_at`, `status`, `balance_cached`.
* **Create sub-account at provider** (if supports subaccounts)

  * Calls provider subaccount create API.
  * Stores returned `provider_account_id`.
* **Sync balance**

  * Calls provider balance endpoint and caches it.
* **Suspend / Activate**

  * Sets local status; optionally call provider to disable subaccount.

All actions must:

* Be idempotent.
* Write to `ProviderRequestLog`.
* Fail safely (don’t overwrite working credentials).

---

## Runtime request flow (per invoice submission)

### Step-by-step

1. **Tenant resolution**

   * django-tenants middleware sets current tenant.
2. **Load provider mapping from public schema**

   * Fetch `TenantProviderAccount` by tenant + provider.
   * Ensure `status == ACTIVE`.
3. **Select auth strategy**

   * `SUBACCOUNT`: use tenant’s credential.
   * `WALLET_ID`: use master credential + tenant wallet_id param.
   * `CLIENT_OWNED_KEYS`: use tenant-provided keys.
4. **Build idempotency key**

   * `"{provider}:{tenant_id}:{invoice_uuid}:{operation}"`.
5. **Call provider**

   * Include idempotency header/field if supported.
   * Include correlation id in headers for tracing.
6. **Persist results**

   * Update invoice status in tenant schema (e.g. SUBMITTED / FAILED).
   * Insert `ProviderRequestLog` in public schema.
7. **Error handling**

   * Map provider error codes to actionable messages:

     * insufficient credits
     * invalid invoice
     * service unavailable
     * auth failure
8. **Retry strategy**

   * Retry only safe categories:

     * network timeouts
     * 5xx
     * provider “pending” states
   * Do not retry validation errors.
   * Use exponential backoff and max attempts.

---

## Credit isolation guarantees (what you must enforce)

Even with Option B, ensure:

* Every request uses the tenant’s mapped bucket:

  * credentials or wallet_id are derived strictly from tenant context, never from user input.
* Hard checks:

  * If mapping missing → block submission.
  * If tenant suspended → block submission.
* Optional pre-check:

  * If provider balance endpoint exists, pre-check low balance and fail fast (avoid partial workflows).

---

## Reconciliation and billing accuracy

### Daily reconciliation job

If provider offers usage reports:

1. Fetch per-subaccount usage (or wallet usage).
2. Compare to your invoice submission logs.
3. Flag mismatches:

   * provider charged but you have no invoice record
   * invoice record exists but provider shows no charge
4. Generate an ops report.

Store reconciliation results in public schema:

* `ReconciliationRun`
* `ReconciliationIssue`

### Balance sync job

Hourly/daily:

* Pull balance for each active tenant mapping.
* Store `balance_cached`, `last_balance_sync_at`.
* Trigger alerts when below thresholds.

---

## Queueing and worker design

### Why

If multiple tenants submit bursts, you need to protect:

* provider API limits
* your app stability
* fairness across tenants

### Plan

* Use a task queue (Celery/RQ/Arq).
* Queue per provider, optionally per tenant:

  * global concurrency limit to provider
  * per-tenant concurrency limit (e.g., max 2 in-flight per tenant)
* Implement:

  * `submit_invoice_task(tenant_id, invoice_id)`
  * `retry_failed_task(...)`
  * `sync_balance_task(tenant_id)`
  * `reconcile_task(date_range)`

---

## Security hardening checklist

1. **Secrets**

   * encryption at rest
   * masked admin UI
   * rotation support
2. **Access**

   * least privilege groups
   * 2FA for admin users (recommended)
3. **Network**

   * outbound allowlist to provider endpoints
   * TLS verification enforced
4. **Audit**

   * admin change log for credential/mapping edits
   * request logs with correlation ids
5. **Tenant isolation**

   * strict tenant context usage
   * automated tests verifying no cross-tenant credential use

---

## Testing plan

### Unit tests

* Mapping validation by mode.
* Encryption/decryption works and never returns plaintext to admin display.
* Request builder selects correct credentials/wallet_id per tenant.
* Idempotency key generation stable.

### Integration tests (mock provider)

* Sub-account creation workflow.
* Balance sync.
* Submission success and error code mapping.
* Retry behavior.

### Multi-tenant safety tests (critical)

* Create two tenants A and B with different mappings.
* Submit invoice under tenant A and assert provider called with A bucket.
* Repeat for B.
* Attempt injection: pass B wallet_id in payload under A; assert ignored.

### Admin tests

* Permission checks: support cannot view/edit secrets.
* Actions produce logs and update status.

---

## Deployment and rollout

### Phase 1: Prepare shared models + admin

* Deploy public schema migrations.
* Add admin screens and permissions.
* Add encryption and logging redaction.

### Phase 2: Wire runtime integration to use TenantProviderAccount

* Feature flag: `USE_PROVIDER_BUCKETS=true`.
* Default to blocking if mapping missing.

### Phase 3: Backfill and onboard tenants

* For each tenant:

  * create provider sub-account or set wallet_id
  * verify connectivity via admin action
  * run a test invoice in sandbox

### Phase 4: Enable balance sync + alerts

* Add scheduled tasks.
* Set thresholds and notifications.

### Phase 5: Reconciliation

* Add usage import and mismatch reporting.

---

## Concrete admin onboarding workflow (what ops will do)

For a new tenant:

1. Create tenant (existing process).
2. In Django admin → TenantProviderAccount → “Add”
3. Select provider, mode (`SUBACCOUNT` or `WALLET_ID`)
4. Enter provider_account_id / wallet_id and credentials (if needed)
5. Save
6. Click action: “Verify credentials”
7. Confirm status becomes ACTIVE and balance cached shows a value
8. Run a sandbox test invoice submission
9. Enable production submissions

---

## What “done” looks like

* Each tenant has an explicit provider mapping in public schema.
* All provider calls derive bucket identifiers strictly from tenant context.
* Admin can:

  * create/update mappings
  * verify connectivity
  * sync balances
  * see per-tenant request logs
* You can prove, via logs, which tenant bucket was used for every invoice.
* Low credit or auth failures are visible immediately and isolated per tenant.

---

If you state which of these Option B variants your provider supports:

* (1) sub-account creation API,
* (2) wallet_id parameter under one master credential,
* (3) client-owned keys,

I can convert the plan into an exact model schema (fields/types), admin configuration (fieldsets/actions), and the request-routing code structure for that variant.
