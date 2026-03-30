# Product Requirements Document
## Stablecoin Payout Rails

**Version:** 1.0  
**Status:** Approved  
**Author:** Smit Patel, Product  
**Collaborators:** Engineering, Compliance, Legal, Finance, GTM

---

## 1. Problem

Enterprise platforms and businesses paying out globally face three core pain points:

1. **Speed** — SWIFT payouts take 2–5 business days. Contractors, suppliers, and partners in SEA, LatAm, and Africa wait days for what should be a near-instant transfer.

2. **Cost** — SWIFT wires cost $25–45/transaction. For high-volume payers (1000+ tx/month), this represents significant unnecessary cost.

3. **Coverage** — ~1.4B people remain unbanked but increasingly have crypto wallets. SWIFT literally cannot reach them; stablecoins can.

---

## 2. Opportunity

Stablecoin payment rails (primarily USDC and USDT) offer:
- Sub-5-minute settlement globally
- <$1 per transaction
- 24/7/365 availability (no banking hours)
- Programmable, auditable transaction trail

The product opportunity is to wrap this technology in an enterprise-ready API with:
- Built-in compliance (AML, KYT, Travel Rule)
- Developer-friendly DX (no chain-specific knowledge required)
- Fiat-like reconciliation experience

---

## 3. Target Users

| Persona | Need | Volume |
|---|---|---|
| Enterprise Platform (marketplace, gig economy) | Pay out to thousands of sellers/contractors globally | 500–5000 tx/day |
| Mid-market Cross-border Business | Replace SWIFT wires for supplier payments | 50–500 tx/day |
| Crypto-Native Company | Programmable treasury payouts in USDC | 10–200 tx/day |

---

## 4. Solution

A multi-chain stablecoin payout API that:
1. Accepts a simple payment intent (amount, currency, beneficiary wallet)
2. Screens the wallet for sanctions and AML risk
3. Selects the optimal blockchain network automatically
4. Executes and monitors to confirmation
5. Returns structured reconciliation data

### Key Design Principles
- **Abstraction over control** — Merchants shouldn't need to think about chains
- **Compliance-first** — Every payout screened before execution, no exceptions
- **Developer experience** — Integration should take <1 day for an experienced developer
- **Auditability** — Every transaction traceable to on-chain tx hash + compliance decision

---

## 5. Funding Model — How Merchants Supply Stablecoins

Enterprise merchants typically hold fiat, not stablecoins. The platform supports two funding paths:

### Path A: Fiat Pre-Funding (Default)
Merchant deposits fiat (USD, EUR, SGD) into a Tazapay holding account. Tazapay on-ramps to USDC via Circle's mint/redeem API or a licensed on-ramp partner (e.g., MoonPay Business, Transak). The USDC is held in the platform custody wallet, earmarked for the merchant's payouts. Merchant sees a fiat-denominated balance on their dashboard — they never interact with stablecoins directly.

### Path B: Direct Stablecoin Funding
Crypto-native merchants send USDC/USDT directly to a merchant-specific deposit address on the supported chain. The platform detects the deposit via webhook listeners (Alchemy Notify), credits the merchant's balance, and the funds are available for payouts immediately.

### Custody Wallet Rebalancing
When payout demand is concentrated on one chain (e.g., 80% Polygon), the platform uses Circle CCTP to rebalance USDC across chains without bridging risk. Rebalancing runs as a background job triggered when any chain's custody wallet drops below 24 hours of projected payout volume.

---

## 6. Phased Delivery

### Phase 1 — Polygon USDC (Weeks 1–6)
**Scope:**
- POST /v1/payouts/stablecoin endpoint (Polygon only)
- Sanctions screening (OFAC) + basic KYT
- Webhook status delivery
- Sandbox environment

**Success criteria:**
- 3 pilot merchants live
- >98% payout success rate
- Avg settlement <3min

### Phase 2 — Solana + Travel Rule (Weeks 7–12)
**Scope:**
- Solana USDC support (for high-volume merchants)
- FATF Travel Rule compliance flow
- Fee estimation endpoint
- Merchant dashboard (basic)

**Success criteria:**
- Travel Rule flow passing regulatory review
- Solana settlement <1min p95

### Phase 3 — Ethereum + USDT + CCTP (Weeks 13–20)
**Scope:**
- Ethereum mainnet (large-value transfers)
- USDT support (Polygon + Ethereum)
- Circle CCTP cross-chain transfers
- Full reconciliation reports

---

## 7. Compliance Framework

### KYT (Know Your Transaction)
- **Provider:** Chainalysis KYT
- **When:** Every payout, before execution
- **Risk scoring:**
  - Score 0–39: AUTO-APPROVE
  - Score 40–74: FLAG for review (4hr SLA), delayed execution
  - Score 75+: BLOCK, compliance team notified

### Sanctions Screening
- OFAC SDN list
- UN Consolidated Sanctions
- EU Consolidated Sanctions
- Refresh frequency: 4 hours (hard block on cache miss)

### Travel Rule (FATF)
- Applies to transfers ≥ $3,000 USD equivalent
- Originator info transmitted to beneficiary VASP if hosted wallet
- Unhosted wallets: enhanced monitoring, self-certification required for >$10K

---

## 8. Success Metrics

### Primary
- **Payout Success Rate** — % of initiated payouts that complete (target: >99%)
- **Avg Settlement Time** — Time from API submission to on-chain confirmation

### Secondary
- Avg fee per transaction (target: <$0.50 blended)
- Developer integration time (time from API key to first successful payout)
- Compliance false positive rate (KYT flagging legitimate transactions)
- Merchant API error rate

---

## 9. Open Questions / Decisions Log

| Question | Decision | Rationale | Date |
|---|---|---|---|
| USDC-first vs USDT-first? | USDC-first | Better regulatory standing, Circle attestations | Q4 2025 |
| Custodial vs non-custodial? | Custodial for transit only | Speed + gas management; no overnight float | Q4 2025 |
| Polygon vs Ethereum as default? | Polygon default | Cost + speed; Eth for large amounts | Q4 2025 |
| Build Travel Rule in-house vs vendor? | Vendor (Notabene) | Regulatory complexity too high to build; TTM priority | Q1 2026 |
