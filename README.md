# 🌐 Stablecoin Payout Rails — Multi-Chain B2B Payout Infrastructure

> A product case study on building enterprise-grade stablecoin payout infrastructure across Polygon, Solana, and Ethereum — enabling cross-border payouts in USDC and USDT with sub-minute settlement.

---

## Overview

Global B2B payouts over SWIFT are slow (2–5 days), expensive ($25–45/transaction), and inaccessible in emerging markets with weak banking rails. 

**Stablecoin Payout Rails** gives enterprises a single API to send USDC/USDT payouts across multiple blockchain networks — with automatic network selection, built-in compliance, and fiat-like reconciliation.

This product was built for:
- **Platforms** paying out to sellers, contractors, or partners globally
- **Enterprises** replacing SWIFT wires to SEA, LatAm, Africa corridors
- **Crypto-native businesses** needing programmable, auditable treasury payouts

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                   STABLECOIN PAYOUT RAILS                          │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    MERCHANT / ENTERPRISE                    │  │
│  │                                                             │  │
│  │   POST /v1/payouts/stablecoin  ──────────────────────────► │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │                  API GATEWAY + AUTH                       │    │
│  │   API Key validation │ Rate limiting │ Idempotency check  │    │
│  └───────────────────────────────────────────────────────────┘    │
│                              │                                     │
│              ┌───────────────┼──────────────────┐                 │
│              ▼               ▼                  ▼                 │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│  │  COMPLIANCE  │  │  WALLET ABSTRAC- │  │  NETWORK         │    │
│  │  LAYER       │  │  TION LAYER      │  │  SELECTOR        │    │
│  │              │  │                  │  │                  │    │
│  │ • Sanctions  │  │ • Merchant       │  │ Polygon  ──────► │    │
│  │   screening  │  │   custody wallet │  │ (default, fast)  │    │
│  │ • Wallet AML │  │ • Address        │  │                  │    │
│  │   (KYT)      │  │   validation     │  │ Solana   ──────► │    │
│  │ • Travel     │  │ • Multi-chain    │  │ (high volume)    │    │
│  │   rule       │  │   routing        │  │                  │    │
│  └──────────────┘  └──────────────────┘  │ Ethereum ──────► │    │
│                                          │ (large amounts)  │    │
│                                          └──────────────────┘    │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │                 EXECUTION ENGINE                          │    │
│  │                                                           │    │
│  │  Sign transaction → Broadcast → Monitor → Confirm        │    │
│  │                                                           │    │
│  │  ┌───────────┐  ┌──────────────┐  ┌──────────────────┐  │    │
│  │  │ Polygon   │  │   Solana     │  │    Ethereum      │  │    │
│  │  │ RPC Node  │  │   RPC Node   │  │    RPC Node      │  │    │
│  │  │ (Alchemy) │  │  (Helius)    │  │    (Alchemy)     │  │    │
│  │  └───────────┘  └──────────────┘  └──────────────────┘  │    │
│  └───────────────────────────────────────────────────────────┘    │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │                 RECONCILIATION & REPORTING                │    │
│  │                                                           │    │
│  │  On-chain event indexing → Canonical ledger → Webhooks   │    │
│  │  Merchant dashboard → Daily settlement reports           │    │
│  └───────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Chain Strategy

### Network Selection Logic

| Condition | Network | Why |
|---|---|---|
| Default / Speed priority | **Polygon** | ~2min finality, $0.01–0.15 fees, EVM-compatible |
| High volume (>1000 tx/day) | **Solana** | 400ms finality, $0.00025/tx, USDC native |
| Large amounts (>$100K) | **Ethereum** | Highest security guarantees, institutional trust |
| Merchant override | Any | Merchant can force network in API request |

### Stablecoin Support

| Stablecoin | Networks | Issuer | Use Case |
|---|---|---|---|
| USDC | Polygon, Ethereum, Solana | Circle | Primary — institutional trust, fully reserved |
| USDT | Polygon, Ethereum, Tron | Tether | Secondary — highest liquidity, broader receiver support |

---

## PM Work — What I Owned

### Discovery
- Interviewed 12 enterprise merchants on cross-border payout pain points
- Mapped current SWIFT payout flow: avg 2.8 days settlement, $34 avg fee
- Benchmarked competitors: Coinbase Commerce, BitPay, Fireblocks — identified DX gaps

### Product Design
- Defined wallet abstraction layer so merchants never think about chain specifics
- Designed network selector logic (above) with eng — merchants pass `network: auto`
- Specified Travel Rule compliance flow for transfers >$3,000 (FATF requirement)
- Designed merchant-facing reconciliation format (mirrors familiar SWIFT MT103 fields)

### Launch Sequencing
- **Phase 1:** Polygon-only (USDC) — lowest risk, lowest cost, fastest integration
- **Phase 2:** Solana (USDC) — for high-volume merchants with volume >500 tx/day
- **Phase 3:** Ethereum (USDC + USDT) — large enterprise, treasury use cases

### Regulatory Navigation
- Worked with legal on MAS (Singapore) digital payment token requirements
- Defined KYT (Know Your Transaction) integration scope with Chainalysis
- Established beneficiary wallet verification SOP for first-time recipients

---

## Key Product Decisions

### Decision 1: Wallet Abstraction vs. Direct Chain Access
**Options considered:**
- A) Expose chain-specific APIs (merchant chooses Polygon vs Ethereum)
- B) Single abstraction endpoint, platform chooses chain

**Decision: Option B (abstraction)**  
Rationale: Most enterprise finance teams don't want to reason about chains. Abstracting it reduces integration friction and lets us optimize routing without breaking merchant integrations. Advanced merchants can override via `network` param.

### Decision 2: USDC-first vs USDT-first
**Decision: USDC-first**  
Rationale: USDC's full-reserve attestations and Circle's regulatory standing make it easier to get compliance sign-off. USDT added in Phase 2 as a secondary option for markets with deeper USDT liquidity.

### Decision 3: Custody Model
**Decision: Non-custodial for merchant funds, custodial for transit**  
Rationale: Merchant sends funds to our custody wallet for execution (needed for gas + speed), but we implement immediate pass-through with no overnight float. Reduces regulatory exposure vs holding merchant balances.

---

## Outcomes (Hypothetical)

| Metric | SWIFT Baseline | Stablecoin Rails |
|---|---|---|
| Avg settlement time | 2.8 days | 3.4 minutes |
| Avg fee per transaction | $34 | $0.18 |
| Markets reachable | 64 | 120+ (wallet address anywhere) |
| Ops interventions / 1000 tx | 22 | 4 |
| Developer integration time | N/A (bank process) | 2.5 days avg |

---

## Simulator

The `/simulator` directory contains a working Python prototype that demonstrates the network selection and compliance logic:

```bash
# Run demo scenarios (7 test cases covering all routing paths)
python simulator/payout_simulator.py --demo

# Interactive mode — input your own payout parameters
python simulator/payout_simulator.py
```

The simulator covers:
- **Network selection**: Amount-based, volume-based, and gas-aware routing
- **Compliance screening**: Sanctions checking, KYT risk scoring, Travel Rule triggers
- **Execution simulation**: Tx hash generation, settlement time estimation
- **Failure paths**: Blocked payouts, flagged-for-review, dead letter queue

Demo scenarios include: standard Philippines payout (→ Polygon), $250K enterprise wire (→ Ethereum), high-volume marketplace (→ Solana), sanctioned wallet (→ blocked), and Travel Rule edge cases.

---

## Repo Structure

```
stablecoin-payout-rails/
├── README.md                    ← You are here
├── docs/
│   ├── prd.md                   ← Full Product Requirements Document
│   ├── network-selection.md     ← Multi-chain routing logic
│   ├── compliance.md            ← KYT, Travel Rule, AML framework
│   └── metrics.md               ← KPIs and instrumentation
├── diagrams/
│   ├── flows.md                 ← Mermaid sequence + flow diagrams
│   └── network-topology.md      ← Multi-chain architecture diagram
├── api-spec/
│   └── openapi.yaml             ← Stablecoin payout API contract
├── simulator/
│   ├── payout_simulator.py      ← Working prototype — network selection + compliance
│   └── agent_simulator.py       ← Agentic payments expansion — MPP/x402 integration
└── workflows/
    ├── polygon-payout.md        ← End-to-end Polygon payout flow
    ├── solana-payout.md         ← Solana-specific considerations
    └── travel-rule.md           ← FATF Travel Rule compliance flow
```

---

## Agentic Payments Expansion

The `/docs/agentic-expansion-strategy.md` proposes three paths for expanding into the agent economy using MPP (Stripe/Tempo) and x402 (Coinbase) protocols:

1. **Last-Mile Rail** — Tazapay as the fiat off-ramp for agent-initiated payments. Agent pays via MPP session → Tazapay converts stablecoin to local fiat → supplier gets paid in PHP/INR/VND.

2. **Agent Wallet Orchestrator** — Managed wallets for enterprise AI agents with spending policies (daily limits, allowed corridors, human approval thresholds). Full compliance screening on every agent payment.

3. **MPP-Discoverable Service** — Tazapay's payout APIs listed in the MPP payments directory. AI agents discover and pay per-payout with zero onboarding.

Run the agent simulator to see all three paths in action:

```bash
python simulator/agent_simulator.py --demo
```

---

## Tech Stack Awareness

| Layer | Technology |
|---|---|
| Polygon RPC | Alchemy (primary), QuickNode (failover) |
| Solana RPC | Helius (primary), Triton (failover) |
| Ethereum RPC | Alchemy |
| USDC Integration | Circle CCTP (Cross-Chain Transfer Protocol) |
| Wallet AML | Chainalysis KYT |
| Gas Estimation | EIP-1559 (ETH/Polygon), compute units (Solana) |
| Event Indexing | Custom webhook listeners + Alchemy Notify |
| Reconciliation | Internal ledger with on-chain tx hash mapping |

---

*This is a product case study combining real cross-border payments experience with hypothetical crypto/stablecoin execution. Built to demonstrate PM thinking on multi-chain architecture, stablecoin product design, compliance, and developer experience.*
