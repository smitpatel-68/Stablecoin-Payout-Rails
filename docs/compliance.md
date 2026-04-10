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

---

## 7. Merchant Onboarding (KYC / KYB / AML)

Merchants are not end-users, but the platform still has to KYC them
because each merchant is a fiduciary relationship and a conduit for funds.
Regulator expectations here come from the same rulebook that covers the
payout beneficiary screening in §1 – §3.

### 7.1 KYB — Know Your Business

Every merchant applying to the platform must clear KYB before a live API
key is issued:

| Artefact | Required for | Verification |
|---|---|---|
| Legal name, jurisdiction of incorporation | All merchants | Registry lookup + corporate documents |
| Company registration number / LEI | All merchants | Companies House / SEC / equivalent registry |
| Proof of address (≤ 90 days old) | All merchants | Utility bill or bank statement |
| Articles of incorporation / bylaws | All merchants | Document collection |
| Source of funds statement | Volume > $500K/month | Narrative + bank statements |
| Financial statements (last 2 years) | Volume > $5M/month | Auditor-issued if available |
| Regulatory licences (MSB, EMI, PSP, VASP) | Regulated verticals | Regulator registry confirmation |

### 7.2 UBO identification

Ultimate beneficial owners are identified for every merchant:

- Any natural person owning **≥ 25%** of the entity is a UBO.
- Any natural person exercising control through other means (board seat,
  veto, senior management) is a UBO.
- For nested structures, the platform traces ownership up to the ultimate
  natural person — shell companies terminate the chain, they do not mask it.
- UBOs are screened against OFAC SDN, UN, EU sanctions lists and the
  platform's PEP (Politically Exposed Person) list at onboarding and
  re-screened daily.

UBO records are T3 (see `docs/data-classification.md`). They are stored
under per-tenant encryption and retained for 7 years after offboarding.

### 7.3 Risk tiering

Each merchant is assigned an internal risk tier at onboarding:

| Tier | Profile | Onboarding requirements | Monitoring |
|---|---|---|---|
| **Low** | Regulated entity in a major jurisdiction, transparent UBO, low-risk vertical | Standard KYB + UBO | Standard |
| **Medium** | SME, opaque vertical, cross-border, or first-time crypto operator | KYB + UBO + source-of-funds narrative | Monthly review |
| **High** | VASP-adjacent, high-risk jurisdiction, nested ownership, or material PEP exposure | Full EDD (Enhanced Due Diligence) + legal review + compliance committee sign-off | Weekly review + lower per-txn limits |

Tiering drives per-merchant rate limits, Travel Rule thresholds, and the
anomaly-detection baselines used for structuring alerts.

### 7.4 Periodic review

KYB information is re-verified on a schedule tied to risk tier:

- **Low risk:** every 24 months
- **Medium risk:** every 12 months
- **High risk:** every 6 months

Any of the following events trigger an **out-of-cycle** review regardless
of the scheduled cadence:

- Change of UBO, directors, or controlling party.
- Change of registered address or jurisdiction.
- Material change in business model or vertical.
- Any SAR filed relating to the merchant (see §8).
- Any sanctions or adverse-media match on the merchant or a UBO.
- Material deviation from expected payout volume or corridor mix.

### 7.5 Offboarding

Offboarding is non-trivial because of the retention requirements:

1. Live API keys are revoked immediately on the offboarding decision.
2. Merchant is given 30 days to drain any pending balance via a final
   payout run — after which the balance is held pending account closure.
3. KYC / UBO records are retained for **7 years** post-offboarding.
4. Audit logs are retained for **7 years** post-offboarding.
5. Beneficiary PII tied to that merchant is crypto-shredded on the
   standard 30-day post-terminal schedule — offboarding does not
   accelerate PII deletion because the payout records themselves are
   retained.

---

## 8. Suspicious Activity Reporting (SAR)

### 8.1 When a SAR is required

A SAR (or the local equivalent — STR in the UK/EU, UTR in Canada) is
filed when the platform knows, suspects, or has reasonable grounds to
suspect that a transaction involves funds from illegal activity, is
intended to disguise the origin of funds, or is structured to evade
reporting.

Concrete SAR triggers at the platform level:

- Sanctions HIT on a beneficiary wallet or name.
- KYT HIGH verdict (score ≥ 75) from Chainalysis.
- Confirmed structuring: multiple payouts from the same merchant to
  related beneficiaries in amounts just below the Travel Rule threshold
  (detected by the pattern detector in §6).
- Suspected merchant key compromise (see runbook §8) involving payouts to
  previously unseen beneficiaries in unusual corridors.
- Adverse media or a regulator referral naming the merchant or a UBO.
- A beneficiary wallet linked to a previously reported incident or on the
  platform's internal watchlist.

### 8.2 Filing timeline

SAR filing is governed by strict regulatory deadlines. The platform's
internal SLA is tighter than any individual regulator's to leave room for
review:

| Step | SLA |
|---|---|
| Detection → compliance triage | 1 business day |
| Triage → draft SAR narrative | 5 business days |
| Draft → internal review (two compliance officers) | 10 business days |
| Internal sign-off → regulator filing | 30 calendar days from detection (hard deadline) |

The 30-day regulatory filing deadline is enforced by an automated ticket
that escalates to the CCO (Chief Compliance Officer) on day 20 if the
filing has not reached internal sign-off.

### 8.3 Tipping-off prohibition

Once a SAR is under consideration, the merchant and the beneficiary
**must not** be informed. This includes via:

- Webhook events. The platform returns the generic `case_id` and a vague
  "under review" status; the webhook payload never references SAR
  activity.
- Support tooling. Support agents see `RESTRICTED` on SAR-flagged payouts
  and are trained to give a non-committal response.
- Dashboard. SAR-flagged payouts display the same `PENDING_COMPLIANCE_REVIEW`
  state as any other review hold.

The tipping-off prohibition is enforced technically by separating the SAR
case database from the merchant-facing data model — the merchant's view
of a payout does not join against the SAR table. Only the compliance plane
can see SAR state.

### 8.4 Ongoing monitoring after a SAR

Filing a SAR does not automatically halt the merchant. The decision to
continue, restrict, or offboard is made by the compliance committee based
on the pattern, the jurisdiction, and the merchant's response to targeted
questions. What **does** change automatically:

- The merchant is moved to **High** risk tier for at least 12 months.
- All payouts above a lowered threshold route to manual review.
- The merchant's UBO list is re-screened weekly instead of daily.
- The compliance audit log is flagged for inclusion in the next
  regulatory examination pack.

### 8.5 Record-keeping

SAR records — the filing itself, the underlying transaction records, and
the investigation notes — are retained for a minimum of **5 years from
the date of filing**, aligned with FinCEN, FCA, and FINTRAC requirements.
In jurisdictions with longer retention mandates (e.g. some EU states: 7
years), the longer period applies. Records are stored in the same
append-only WORM store as the compliance audit log and are subject to the
same access controls as T3 data.
