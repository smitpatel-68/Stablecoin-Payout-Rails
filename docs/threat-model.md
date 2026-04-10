# Threat Model
## Stablecoin Payout Rails — STRIDE Analysis

This document catalogues the threats to the stablecoin payout platform using
STRIDE (Spoofing, Tampering, Repudiation, Information disclosure, Denial of
service, Elevation of privilege) and maps each to the control that mitigates
it. It complements `docs/compliance.md` (regulatory threats) and
`docs/runbook.md` (operational response).

The model assumes the architecture described in the README and
`diagrams/network-topology.md`: a merchant calls a hosted API gateway, which
fans out to a compliance layer, a wallet abstraction layer, a network
selector, and a per-chain execution engine signing from HSM-backed custody
wallets.

---

## 1. Assets

| Asset | Sensitivity | Where it lives |
|---|---|---|
| Custody wallet private keys | **Critical** — theft drains float | HSM only; never in application memory |
| API signing secrets (merchant HMAC) | **Critical** — impersonation | Merchant side + platform DB (encrypted) |
| API keys (`sk_live_`, `sk_test_`) | High — request forgery | Merchant side + platform DB (hashed) |
| Beneficiary PII (name, wallet, country) | High — regulated PII + link to chain | Encrypted at rest, see `docs/data-classification.md` |
| Compliance audit log | High — regulatory evidence | Append-only WORM store |
| Stablecoin balances in custody | **Critical** — the float itself | On-chain |
| Merchant idempotency cache | Medium — double-pay risk if evicted | Redis with 24h TTL |
| Sanctions list snapshots | Medium — staleness → enforcement gap | In-memory + WORM archive |

---

## 2. Trust boundaries

```
┌─────────────────┐   TLS 1.2+   ┌─────────────────┐   VPC-internal   ┌─────────────────┐
│ Merchant app    │─────────────▶│ API gateway     │─────────────────▶│ Core services   │
│ (untrusted)     │              │ (edge)          │                  │ (trusted)       │
└─────────────────┘              └─────────────────┘                  └─────────────────┘
                                                                               │
                                 ┌─────────────────┐   TLS 1.2+        ┌───────┴────────┐
                                 │ Chainalysis     │◀──────────────────│ Compliance     │
                                 │ Notabene        │                   │ layer          │
                                 │ OFAC feed       │                   └────────────────┘
                                 └─────────────────┘                           │
                                                                       ┌───────┴────────┐
                                 ┌─────────────────┐                   │ Execution      │
                                 │ Alchemy/Helius  │◀──────────────────│ engine         │
                                 │ QuickNode/Triton│                   └────────────────┘
                                 └─────────────────┘                           │
                                                                       ┌───────┴────────┐
                                                                       │ HSM            │
                                                                       │ (no network)   │
                                                                       └────────────────┘
```

The key boundaries are:

1. **Merchant ↔ API gateway** — untrusted caller, trusted server.
2. **API gateway ↔ core services** — trusted internal, still enforce authz.
3. **Core services ↔ compliance vendors** — trusted server, third-party vendor.
4. **Core services ↔ RPC providers** — trusted server, third-party vendor
   that can lie about on-chain state.
5. **Execution engine ↔ HSM** — trusted server, air-gapped HSM.

---

## 3. STRIDE

### S — Spoofing

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| S1 | Attacker replays a captured `POST /payouts/stablecoin` request | HMAC signing with 5-minute timestamp window; replay cache on signatures | Low |
| S2 | Attacker steals an API key and forges requests | Scoped keys; HMAC secret is separate from API key; 90-day rotation; rate-limit + anomaly detection | Medium (secrets can still leak) |
| S3 | Attacker forges a webhook to the merchant claiming a payout completed | Outbound `Tazapay-Signature` HMAC; merchants must verify and dedupe on `Tazapay-Event-Id` | Merchant implementation risk |
| S4 | Attacker spoofs the beneficiary wallet via address poisoning / homoglyph | First-time-beneficiary warning; optional 24h delay above a threshold; rolling allowlist | Medium |
| S5 | Attacker spoofs OFAC / sanctions feed | Signature verification on the list; archive + hash-chain; refresh failure → hard block | Low |
| S6 | Attacker spoofs an RPC provider response (e.g. fake `tx_hash`) | Cross-check against failover RPC on critical queries; format/range sanity checks | Low |

### T — Tampering

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| T1 | Request body modified in transit | TLS 1.2+ + HMAC body hash in signature | Very low |
| T2 | Compliance audit log edited after the fact | Append-only WORM store with hash chain; access via separate audit plane | Low |
| T3 | Idempotency cache poisoning (attacker writes a bogus replay) | Cache is write-through from the API gateway only; no external writers | Low |
| T4 | Merchant metadata used as an injection vector (SQL/XSS) in dashboards | Metadata is stored as opaque strings and rendered with context-aware escaping; 500-byte cap per value | Low |
| T5 | Gas-price oracle manipulation forces Tron fallback (higher risk chain) | Tron is opt-in and requires USDT; secondary oracle cross-check before failover | Low |
| T6 | Reorg on Polygon / Ethereum reverts a "completed" payout | Confirmation depth scales with amount; 5-minute post-finality monitor; rollback triggers refund + compliance review | Medium on large payouts |

### R — Repudiation

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| R1 | Merchant denies submitting a payout | Signed request stored with hash + timestamp; 7-year retention | Low |
| R2 | Platform denies a compliance decision to a regulator | Immutable compliance log with decision, inputs, vendor response, and SLA latency | Low |
| R3 | Vendor (Chainalysis / Notabene) denies a screening response | Request/response pair stored with vendor signature / response ID | Low |
| R4 | Merchant denies receipt of a webhook | Webhook delivery log retained 90 days; redelivery UI available | Low |

### I — Information disclosure

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| I1 | Cross-merchant read of payout detail | `GET /payouts/{id}` returns `404` (not `403`) for foreign IDs; tenancy enforced at the ORM layer | Low |
| I2 | Error messages leak internal logic (e.g. "wallet flagged by KYT score 82") | Production returns vague errors + `case_id`; detailed errors only in sandbox | Low |
| I3 | Beneficiary PII exposed via logs | Per-field classification in `docs/data-classification.md`; log redaction middleware; no PII in `metadata` | Medium (hygiene-dependent) |
| I4 | On-chain mempool broadcasts the payout amount before confirmation | Acknowledged; acceptable for USDC/USDT transfers (no price-impact MEV) | Accepted |
| I5 | SSRF via `webhook_url` exfiltrating internal metadata (e.g. `169.254.169.254`) | Rebinding-safe resolver; RFC1918/link-local/loopback rejected; no redirects | Low |
| I6 | Enumeration of `payout_id` values across merchants | IDs are CSPRNG-derived (`secrets`), 12+ chars from a 36-char alphabet (~62 bits entropy); tenancy check on read | Low |
| I7 | Secrets committed to git | `.gitignore`, pre-commit `gitleaks` / `detect-secrets`, `SECURITY.md` disclosure flow | Low |

### D — Denial of service

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| D1 | Volumetric request flood exhausts the API gateway | Edge rate limiting + WAF; per-API-key token bucket; 429 with `Retry-After` | Low |
| D2 | Large-body attack (giant `metadata`) exhausts memory | 1 MB request cap; `metadata` ≤ 20 keys × 500 bytes; 413 on breach | Low |
| D3 | Chainalysis / Notabene outage halts every payout (fail-closed) | Documented SLA + secondary vendor on standby; Service Unavailable response with realistic `Retry-After`; see `docs/runbook.md` | Accepted (fail-closed is the correct posture) |
| D4 | RPC primary + failover both down for a chain | Queue + retry loop; automatic 10-minute backoff; ops paged at 2h; see runbook | Medium (chain-wide) |
| D5 | Polygon gas spike cascades into queue buildup | Tron fallback for opt-in USDT; queue-with-retry for the rest; alert at queue depth > 5,000 | Medium |
| D6 | Custody wallet drained → subsequent payouts fail for lack of funds | Balance monitor at 48h-of-volume floor; auto-rebalance via CCTP; kill-switch to block new payouts before on-chain failure | Low |
| D7 | Compliance review backlog stalls medium-risk payouts | On-call rotation + 4h SLA; automated fallback to block with appeal after SLA expiry | Medium |

### E — Elevation of privilege

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| E1 | `payouts:read` key used to create a payout | Scope enforced at the API gateway; 403 on write with read-only key | Low |
| E2 | `sk_test_` key used against production host (or vice versa) | Host-level prefix check rejects at the edge | Low |
| E3 | Compromised internal service impersonates the execution engine and signs a payout | HSM requires a per-request signed authorization token from the execution engine; authz tokens are short-lived; all signing operations logged | Low |
| E4 | Compromised HSM operator exfiltrates keys | FIPS 140-2 L3 HSM; keys never exit module; m-of-n quorum for HSM admin operations; geographically separated backup HSM | Low |
| E5 | Privilege escalation via dependency supply-chain compromise | Dependency pinning + SBOM; `pip-audit` / Dependabot in CI; review of any dependency added to the signing path | Medium (supply chain is hard) |
| E6 | Insider abuses compliance review UI to clear a blocked payout | Four-eyes review on any unblock; full audit log; anomaly detection on reviewer decisions | Medium |

---

## 4. Top five residual risks

Ranked by combined likelihood × impact:

1. **Supply-chain compromise** (E5) — reaching the signing path via a
   compromised dependency. Mitigated but not eliminated. Invest in SBOM +
   reproducible builds + code review on any package used by the execution
   engine.
2. **Reorg on large Ethereum payouts** (T6) — a $250K payout reorged after
   being marked `COMPLETED` is a real scenario at shallow confirmation
   depth. Confirmation depth must scale with amount.
3. **Compliance vendor outage** (D3) — fail-closed is the right posture but
   it shifts the risk from "a bad payout slips through" to "every payout
   halts". Secondary vendor + clear runbook are the only mitigation.
4. **Insider abuse of compliance review** (E6) — hardest to mitigate with
   technology alone. Four-eyes review is necessary but not sufficient;
   periodic audit of reviewer decisions is required.
5. **Address poisoning / homoglyph attacks** (S4) — beneficiary address
   substitution is a real problem in crypto payments. First-time warnings
   and rolling allowlists help but a motivated attacker can beat them.

---

## 5. Out of scope for this model

- **Physical security of the HSM site** — covered by the data-center
  provider's SOC 2 report.
- **Regulatory policy changes** — tracked in the compliance roadmap, not
  here.
- **Merchant-side security** — we document expectations (HMAC verification,
  PII handling) but do not audit merchant implementations. Merchants are
  responsible for their own webhook endpoint security.
- **Stablecoin issuer failure** (Circle / Tether insolvency) — a business
  continuity question, not a technical threat.

---

## 6. Review cadence

This model is reviewed:

- Quarterly, as part of the security team's regular cadence.
- Whenever a new protocol, chain, or compliance vendor is added.
- Whenever a new asset class (custody model, agent wallets, etc.) is
  introduced — in particular, the agentic expansion (`docs/agentic-
  expansion-strategy.md`) will need its own STRIDE pass before Phase 2
  ships.
- After any security incident, as part of the post-mortem.
