# FATF Travel Rule — Compliance Workflow
## Implementation for Stablecoin Payouts ≥ $3,000

---

## Regulatory Basis

The FATF Travel Rule (Recommendation 16, revised June 2025) requires Virtual Asset Service Providers (VASPs) to transmit originator and beneficiary information for transfers above jurisdictional thresholds.

For our platform, this applies to every stablecoin payout ≥ $3,000 USD equivalent.

---

## Implementation Partner

**Notabene** — Travel Rule protocol provider

Selected over building in-house due to:
- Pre-built VASP directory (5,000+ registered VASPs globally)
- IVMS 101 message format handling
- Multi-jurisdiction threshold management
- Sunrise rule support (handling jurisdictions where counterparty VASPs aren't yet compliant)

---

## Decision Flow

```
Payout submitted
    │
    ▼
Amount ≥ $3,000?
    │
    ├── NO → Skip Travel Rule. Proceed to execution.
    │
    └── YES → Identify wallet type
                │
                ├── HOSTED (exchange/VASP wallet)
                │       │
                │       ▼
                │   Look up VASP in Notabene directory
                │       │
                │       ▼
                │   Send originator info (IVMS 101)
                │       │
                │       ├── VASP acknowledges → Travel Rule satisfied ✓
                │       │
                │       └── VASP unresponsive (24hr timeout)
                │               │
                │               ▼
                │           Apply sunrise rule: proceed with
                │           enhanced monitoring + log non-compliance
                │
                └── UNHOSTED (self-custody wallet)
                        │
                        ▼
                    Amount ≥ $10,000?
                        │
                        ├── NO → Proceed with enhanced monitoring
                        │        Flag for post-transaction review
                        │
                        └── YES → Require self-certification
                                  Merchant must confirm beneficiary
                                  was verified through their KYC process.
                                  Payout held until certification received.
```

---

## IVMS 101 — Data Transmitted

For hosted wallet transfers, we transmit the following in IVMS 101 format:

### Originator Information (sent to beneficiary VASP)
```json
{
  "originator": {
    "originatorPersons": [{
      "naturalPerson": {
        "name": {
          "nameIdentifier": [{
            "primaryIdentifier": "Merchant Legal Name",
            "nameIdentifierType": "LEGL"
          }]
        }
      }
    }],
    "accountNumber": ["merchant_account_id"],
    "originatorVASP": {
      "name": "Tazapay Pte Ltd",
      "lei": "PLATFORM_LEI_NUMBER",
      "nationalIdentification": {
        "nationalIdentifier": "PLATFORM_REG_NUMBER",
        "nationalIdentifierType": "LEIX"
      }
    }
  }
}
```

### Beneficiary Information (received from beneficiary VASP)
```json
{
  "beneficiary": {
    "beneficiaryPersons": [{
      "naturalPerson": {
        "name": {
          "nameIdentifier": [{
            "primaryIdentifier": "Beneficiary Name",
            "nameIdentifierType": "LEGL"
          }]
        }
      }
    }],
    "accountNumber": ["beneficiary_wallet_address"]
  }
}
```

---

## Self-Certification (Unhosted Wallets ≥ $10K)

When a payout to an unhosted wallet exceeds $10,000, we require the merchant to submit a self-certification:

**Merchant certifies that:**
1. The beneficiary has been identified and verified through the merchant's own KYC process
2. The merchant holds documentation supporting the beneficiary's identity
3. The merchant will produce this documentation upon request by the platform or regulators

**Implementation:**
- API returns `422` with `code: TRAVEL_RULE_REQUIRED` and `remediation: "Submit self-certification via /v1/payouts/{id}/certify"`
- Merchant POSTs certification with reference to their internal KYC record
- Platform records certification + timestamp
- Payout released for execution

---

## Jurisdictional Thresholds

The platform applies the **stricter** of FATF and local jurisdiction thresholds:

| Jurisdiction | Threshold | Applied When |
|---|---|---|
| FATF default | $3,000 | Fallback for unlisted jurisdictions |
| EU (MiCA) | €0 (all transfers) | Originator OR beneficiary in EU |
| Singapore (MAS) | SGD 1,500 (~$1,100) | Either party in Singapore |
| UK (FCA) | £1,000 (~$1,250) | Either party in UK |
| Canada (FINTRAC) | CAD 1,000 (~$730) | Either party in Canada |
| UAE (VARA) | AED 3,500 (~$950) | Either party in UAE |

When the originator and beneficiary are in different jurisdictions, we apply the lower (stricter) threshold.

---

## Audit & Retention

- All Travel Rule messages (sent and received) are stored for 7 years
- Self-certifications are stored alongside payout records
- Quarterly reporting to compliance team: Travel Rule trigger rate, completion rate, sunrise rule invocations, self-certification volume
