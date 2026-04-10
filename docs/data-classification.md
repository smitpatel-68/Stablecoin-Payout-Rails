# Data Classification & Handling

Every field the platform stores, logs, or transmits is assigned one of four
sensitivity tiers. This document is the source of truth for what can be
logged, what must be encrypted, and how long each field is retained.

It complements `docs/compliance.md` (which covers the regulatory framework)
and `docs/threat-model.md` (which covers the attack surface).

---

## 1. Sensitivity tiers

| Tier | Label | Examples | Default handling |
|---|---|---|---|
| **T0** | Public | Product docs, OpenAPI spec, marketing copy | No restriction |
| **T1** | Internal | Network topology, gas thresholds, routing decisions | Internal-only; safe to log |
| **T2** | Confidential | Merchant names, payout amounts, transaction hashes, API key **hashes** | Encrypted at rest; access-controlled; never in public logs |
| **T3** | Restricted | Beneficiary PII, merchant UBO info, API **secrets**, signing secrets, private keys | Encrypted at rest with per-tenant keys; HSM-managed where applicable; strict access logging; never in any log |

The default for a new field is **T2 Confidential**. Fields must be explicitly
demoted to T1 or T0.

---

## 2. Field classification

### Request fields (inbound, `POST /payouts/stablecoin`)

| Field | Tier | Encrypted at rest | Loggable? | Notes |
|---|---|---|---|---|
| `X-API-Key` header | T3 | Hashed (argon2id) | Hash only | Never log raw value |
| `X-Signature` header | T3 | Not stored | Last 8 chars only | For replay dedupe |
| `X-Signature-Timestamp` | T1 | N/A | Yes | |
| `Idempotency-Key` | T2 | Yes (per-merchant cache) | Yes | Used for merchant support |
| `amount.value` | T2 | Yes | Yes | Used in dashboards + audit |
| `amount.currency` | T1 | N/A | Yes | |
| `beneficiary.wallet_address` | T2 | Yes | Yes (truncated in logs) | Considered PII when linked to a name |
| `beneficiary.name` | **T3** | Yes (per-tenant key) | **No** — redacted in all logs | Regulated PII |
| `beneficiary.entity_type` | T1 | N/A | Yes | |
| `network` | T1 | N/A | Yes | |
| `webhook_url` | T2 | Yes | Host-only in logs | Full URL only in the merchant's own audit view |
| `metadata.*` | T2 | Yes | Yes | Merchants are warned **not to put PII here** |
| `tron_fallback_enabled` | T1 | N/A | Yes | |

### Response fields (outbound)

| Field | Tier | Notes |
|---|---|---|
| `payout_id` | T1 | Public per-tenant, CSPRNG-derived |
| `status` | T1 | |
| `network_selected` | T1 | |
| `compliance.sanctions_check` | T2 | Merchant can see their own |
| `compliance.kyt_risk_score` | **T3** | Only the verdict (`LOW`/`MEDIUM`/`HIGH`) is returned to the merchant — the raw score is internal only |
| `compliance.kyt_verdict` | T2 | Returned to merchant |
| `execution.tx_hash` | T2 | Returned to merchant; public on-chain anyway |
| `execution.fee_paid_usd` | T2 | Returned to merchant |

### Internal fields (never exposed via the API)

| Field | Tier | Notes |
|---|---|---|
| Custody wallet private key | T3 | HSM only |
| HSM access token | T3 | Short-lived (< 60s); never logged |
| Merchant signing secret | T3 | Hashed + encrypted; rotated on merchant request |
| Webhook secret | T3 | Hashed + encrypted; rotated on merchant request |
| Compliance vendor API keys | T3 | Secret manager; rotated every 90 days |
| RPC provider API keys | T3 | Secret manager; rotated every 90 days |
| Merchant KYC documents | T3 | Encrypted object store; 7-year retention |
| Merchant UBO info | T3 | Encrypted; access logged; 7-year retention |
| Compliance audit log | T2 | Append-only WORM; 7 years |
| API access log | T2 | 6 months |
| Webhook delivery log | T2 | 90 days |
| Error log / stack traces | T2 | 90 days; PII redaction in place |

---

## 3. Encryption at rest

| Tier | Requirement |
|---|---|
| T0 | Optional (convenience only) |
| T1 | Database-level encryption (TDE) |
| T2 | TDE + per-tenant encryption key (envelope encryption) |
| T3 | TDE + per-tenant key + **column-level** AES-256-GCM with key in HSM; decryption logged |

Per-tenant keys are rotated every 90 days. Rotation is zero-downtime via
envelope-encryption re-keying.

---

## 4. Retention & deletion

| Data | Retention | Rationale |
|---|---|---|
| Beneficiary PII (`name`, `entity_type`) | 30 days after payout reaches a terminal state, then cryptographically erased by destroying the tenant key for that row | Regulator accepts crypto-shred |
| Payout record (no PII) | 7 years | Regulatory minimum |
| Compliance audit log | 7 years, then archived to cold storage indefinitely | Regulatory minimum |
| Merchant KYC / UBO | 7 years after merchant offboarding | Regulatory minimum |
| API access log | 6 months | Incident investigation |
| Webhook delivery log | 90 days | Incident investigation |
| Error log | 90 days, PII redacted at ingestion | Debugging |
| Idempotency cache | 24 hours | Spec window |

Retention is enforced by a daily job that scans tables and runs the deletion
or crypto-shred. A dry-run of every deletion runs first and must be approved
by two engineers for T3 data.

---

## 5. Access control

| Tier | Who can read |
|---|---|
| T0 | Everyone |
| T1 | Any employee, read-only by default |
| T2 | Role-based, with access reviewed quarterly |
| T3 | Named individuals only; every access generates an audit event; reviewed monthly |

T3 read access from application code is mediated by a decryption service
that enforces per-request justification (e.g. "compliance screening for
payout po_xxx") and rate-limits decrypt calls. Bulk export of T3 data is
disabled at the platform level.

---

## 6. Logging rules

Three rules, in order of priority:

1. **Never log T3 data.** The logging library has a redaction middleware
   that strips known T3 fields before writing. New T3 fields must be added
   to the redaction allowlist as part of the same PR that introduces them.
2. **Truncate T2 identifiers.** Wallet addresses are logged as the first
   6 and last 4 characters. Transaction hashes are logged as the first 10
   characters. Full values are only available in the merchant's own audit
   view.
3. **Hash T3 identifiers when a reference is needed.** If a log line needs
   to correlate to a T3 field, use a SHA-256 prefix of the value, not the
   value itself.

Violations of these rules are caught by a CI check (`scripts/lint-logs.py`)
that greps for known T3 field names in log statements.

---

## 7. PII in `metadata`

The `metadata` field on `PayoutRequest` is a common leakage vector. The
documented merchant contract is:

> `metadata` is surfaced in logs, dashboards, and support tooling. Do not
> put PII (names, national IDs, bank account numbers) here. Use it for
> internal references only (invoice ID, order ID, SKU).

The platform cannot detect every PII leak into `metadata`, but we run a
daily scan for high-entropy strings and common PII patterns (SSN, IBAN,
email) against `metadata` values and alert the compliance team on matches.

---

## 8. Review cadence

This document is reviewed:

- Whenever a new field is added to any API schema or database table.
- Quarterly, in sync with the threat model review.
- After any incident involving data exposure.
