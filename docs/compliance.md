# Compliance Framework
## AML, Sanctions, KYT, and Travel Rule

---

## Overview

Every stablecoin payout is screened before execution — no exceptions. The compliance layer runs three checks in parallel, and all must pass before the payout proceeds to network selection.

---

## 1. Sanctions Screening

**Lists checked:**
- OFAC SDN (Specially Designated Nationals) list
- UN Consolidated Sanctions list
- EU Consolidated Sanctions list

**Refresh frequency:** Every 4 hours. If the cache is stale (missed refresh), all payouts are hard-blocked until refresh completes.

**Matching logic:**
- Wallet address exact match against known sanctioned addresses
- Beneficiary name fuzzy match (Levenshtein distance ≤ 2) against entity names on sanctions lists
- Country of beneficiary checked against comprehensively sanctioned jurisdictions (DPRK, Iran, Syria, Cuba, Crimea region)

**Outcomes:**
| Result | Action |
|---|---|
| HIT | Hard block. No retry. Compliance team alerted immediately. Merchant receives `SANCTIONS_HIT` webhook. |
| CLEAR | Proceed to KYT screening. |

---

## 2. KYT — Know Your Transaction (Chainalysis)

**Provider:** Chainalysis KYT (Know Your Transaction)

**When:** Every payout, after sanctions screening passes.

**What it checks:** The beneficiary wallet address is scored based on:
- Exposure to darknet markets, mixers, or sanctioned entities
- Transaction history patterns (high-risk services, gambling, etc.)
- Counterparty risk (wallets that have interacted with flagged addresses)

**Risk scoring and actions:**

| Score Range | Verdict | Action | SLA |
|---|---|---|---|
| 0 – 39 | LOW | Auto-approve. Proceed to execution. | Immediate |
| 40 – 74 | MEDIUM | Flag for manual review. Payout delayed. | 4 hours |
| 75 – 100 | HIGH | Block. Compliance team notified. | 15 minutes (to review) |

**False positive handling:** Medium-risk flags are reviewed by the compliance team. If cleared, the wallet is added to a merchant-specific allowlist for 90 days to avoid repeat flagging.

---

## 3. FATF Travel Rule

**Trigger:** Any payout ≥ $3,000 USD equivalent.

**Standard:** FATF Recommendation 16 (revised June 2025). Implemented via Notabene Travel Rule protocol.

### Flow for Hosted Wallets (Exchange/VASP)

When the beneficiary wallet is identified as belonging to a registered VASP (checked against Notabene's VASP directory, OpenVASP, and TRP):

1. Originator information transmitted in IVMS 101 format:
   - Originator name, address, account identifier
   - Originating VASP identifier (LEI or registration number)
2. Beneficiary VASP acknowledges receipt
3. Beneficiary information returned (name, account identifier)
4. Travel Rule satisfied → proceed to execution

### Flow for Unhosted Wallets (Self-Custody)

When the beneficiary wallet is not associated with any known VASP:

| Amount | Action |
|---|---|
| $3,000 – $9,999 | Proceed with enhanced transaction monitoring. Flag for post-transaction review. |
| ≥ $10,000 | Require self-certification from merchant: written confirmation that the beneficiary has been verified through the merchant's own KYC process. Payout held until certification received. |

### Jurisdictional Variations (as of 2026)

| Jurisdiction | Travel Rule Status | Threshold | Notes |
|---|---|---|---|
| EU (MiCA) | Mandatory | €0 (all transfers) | Stricter than FATF — applies to all amounts |
| Singapore (MAS) | Mandatory | SGD 1,500 | Aligned with FATF |
| US (GENIUS Act) | Mandatory (H2 2026) | $3,000 | Pending final rules |
| UK (FCA) | Mandatory | £1,000 | |
| UAE (VARA) | Mandatory | AED 3,500 | |
| Canada (FINTRAC) | Mandatory | CAD 1,000 | |

---

## 4. Compliance Audit Log

Every compliance decision is logged immutably:

```json
{
  "payout_id": "po_01HXYZ...",
  "timestamp": "2025-03-15T10:22:33Z",
  "sanctions": {
    "result": "CLEAR",
    "lists_checked": ["OFAC_SDN", "UN_CONSOLIDATED", "EU_CONSOLIDATED"],
    "list_version": "2025-03-15T08:00:00Z"
  },
  "kyt": {
    "provider": "chainalysis",
    "risk_score": 12,
    "verdict": "LOW",
    "wallet_address": "0x7a3B9c2D..."
  },
  "travel_rule": {
    "triggered": true,
    "amount_usd": 5000,
    "wallet_type": "unhosted",
    "action": "ENHANCED_MONITORING",
    "protocol": "notabene"
  },
  "overall_decision": "CLEARED",
  "decision_latency_ms": 342
}
```

**Retention:** 7 years (regulatory requirement across most jurisdictions).

---

## 5. Tron-Specific Compliance Considerations

Tron is used as a gas-spike fallback for USDT payouts. It requires additional scrutiny:

**Elevated risk profile:** Tron's USDT ecosystem has disproportionate exposure to sanctioned entities and illicit finance. TRM Labs and Chainalysis both flag Tron-based USDT transfers at higher rates than EVM-chain equivalents.

**Enhanced screening for Tron payouts:**
- KYT screening applies to all Tron payouts (same as other chains)
- Additional check: Tron wallet exposure analysis — if the beneficiary wallet has >5% exposure to OFAC-flagged addresses in the last 90 days, the payout is blocked regardless of KYT score
- Tron payouts are flagged in the reconciliation report with a `TRON_FALLBACK` tag for post-hoc compliance review

**Policy:** Tron is never the primary rail. It activates only when Polygon gas exceeds 500 gwei and the merchant has opted into Tron fallback. Merchants must explicitly enable Tron via dashboard settings — it is not enabled by default.

---

## 6. Ongoing Monitoring

Beyond per-transaction screening, the platform runs:

- **Daily wallet re-screening**: All beneficiary wallets paid in the last 90 days are re-checked against updated sanctions lists
- **Pattern detection**: Structuring alerts if a merchant splits payments to stay below Travel Rule thresholds
- **Quarterly compliance review**: KYT false positive rates, sanctions list update cadence, Travel Rule completion rates
