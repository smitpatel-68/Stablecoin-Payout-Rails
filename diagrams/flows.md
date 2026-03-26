# Stablecoin Payout Rails — Flow Diagrams

All diagrams in [Mermaid](https://mermaid.js.org/) format. Render at [mermaid.live](https://mermaid.live) or in GitHub markdown preview.

---

## 1. End-to-End Payout Flow (Happy Path — Polygon)

```mermaid
sequenceDiagram
    participant M as Merchant API
    participant GW as API Gateway
    participant CL as Compliance Layer
    participant WA as Wallet Abstraction
    participant NS as Network Selector
    participant EX as Execution Engine
    participant PG as Polygon Network
    participant RC as Reconciliation

    M->>GW: POST /v1/payouts/stablecoin
    Note over M,GW: {amount: 5000, currency: USDC,<br/>beneficiary_wallet: 0xRecipient..., network: auto}
    GW-->>M: 202 Accepted {payout_id: po_xyz}

    GW->>CL: Screen wallet 0xRecipient
    CL->>CL: OFAC sanctions check ✓
    CL->>CL: Chainalysis KYT: risk_score=8 (LOW) ✓
    CL-->>GW: CLEARED

    GW->>WA: Validate + resolve wallet
    WA->>WA: Checksum address ✓
    WA->>WA: Check for contract vs EOA
    WA-->>GW: wallet_valid=true, type=EOA

    GW->>NS: Select network for $5,000 USDC
    NS->>NS: Amount < $100K → not Ethereum
    NS->>NS: Volume today: 300 tx → not Solana threshold
    NS->>NS: Gas: Polygon 150 gwei ✓
    NS-->>GW: network=POLYGON, est_fee=$0.12, est_time=2min

    GW->>EX: Execute transfer
    EX->>EX: Build USDC transfer calldata
    EX->>EX: Estimate gas + add 20% buffer
    EX->>PG: Broadcast signed transaction
    PG-->>EX: tx_hash: 0xabc123...

    loop Await Confirmations
        EX->>PG: eth_getTransactionReceipt
        PG-->>EX: confirmations: 1 → 2 → 3 ✓
    end

    EX->>RC: Settlement confirmed
    Note over RC: {tx_hash, block: 54291034,<br/>fee_paid: $0.11, settled_at: T+1m42s}

    RC->>M: Webhook: payout.completed
    Note over M: {payout_id, tx_hash, network, fee, settled_at}
```

---

## 2. Multi-Chain Network Selection

```mermaid
flowchart TD
    A[Payout Request] --> B{Merchant specified network?}
    B -->|Yes| C[Use specified network]
    B -->|No: network=auto| D{Amount > $100K?}

    D -->|Yes| E[Ethereum Mainnet]
    E --> F[USDC ERC-20 transfer]

    D -->|No| G{Daily volume > 500 tx?}
    G -->|Yes| H[Solana]
    H --> I[USDC SPL transfer via Circle]

    G -->|No| J{Polygon gas < 500 gwei?}
    J -->|Yes| K[Polygon — DEFAULT]
    K --> L[USDC ERC-20 on Polygon]

    J -->|No: gas spike| M{Tron fallback enabled?}
    M -->|Yes| N[Tron — USDT only]
    M -->|No| O[Queue + retry in 10min]
    O --> J
```

---

## 3. FATF Travel Rule Flow (Transfers > $3,000)

```mermaid
sequenceDiagram
    participant M as Merchant
    participant API as Platform
    participant TR as Travel Rule Engine
    participant VE as VASP Exchange (Beneficiary)
    participant EX as Execution Engine

    M->>API: Payout $5,000 USDC to 0xBeneficiary
    API->>TR: Trigger Travel Rule check (> $3,000)
    
    TR->>TR: Identify if 0xBeneficiary is hosted wallet
    Note over TR: Check VASP directory (OpenVASP / TRP)
    
    alt Beneficiary is hosted wallet (exchange)
        TR->>VE: Send originator info (IVMS 101 format)
        Note over TR,VE: {originator name, address, account ID}
        VE-->>TR: Acknowledged / Beneficiary info returned
        TR-->>API: Travel Rule satisfied ✓
        API->>EX: Proceed with execution
    
    else Beneficiary is unhosted wallet
        TR->>TR: Apply unhosted wallet policy
        Note over TR: Amount < $10K → Proceed with enhanced monitoring
        Note over TR: Amount > $10K → Require self-certification from merchant
        TR-->>API: Policy applied ✓
        API->>EX: Proceed with execution + flag for monitoring
    end
```

---

## 4. System Architecture — Multi-Chain

```mermaid
graph TB
    subgraph Merchants
        M1[Enterprise Platform]
        M2[Marketplace]
        M3[Crypto Native Co]
    end

    subgraph Stablecoin Payout Rails Platform
        GW[API Gateway]
        CL[Compliance Layer<br/>Sanctions + KYT + Travel Rule]
        WA[Wallet Abstraction]
        NS[Network Selector]
        
        subgraph Execution
            EP[Polygon Engine]
            ES[Solana Engine]
            EE[Ethereum Engine]
        end
        
        RC[Reconciliation + Ledger]
        WH[Webhook Dispatcher]
    end

    subgraph Blockchain Networks
        PG[Polygon Mainnet<br/>via Alchemy]
        SL[Solana Mainnet<br/>via Helius]
        ET[Ethereum Mainnet<br/>via Alchemy]
    end

    subgraph Compliance Services
        CH[Chainalysis KYT]
        OF[OFAC API]
        TR[Travel Rule Protocol]
    end

    M1 & M2 & M3 --> GW
    GW --> CL
    CL --> CH & OF & TR
    CL -->|Cleared| WA
    WA --> NS
    NS --> EP & ES & EE
    EP --> PG
    ES --> SL
    EE --> ET
    PG & SL & ET -->|Confirmations| RC
    RC --> WH
    WH --> M1 & M2 & M3
```

---

## 5. USDC Cross-Chain Transfer (Circle CCTP)

```mermaid
sequenceDiagram
    participant M as Merchant Wallet
    participant CB as Circle Bridge (CCTP)
    participant SRC as Source Chain (Ethereum)
    participant DST as Dest Chain (Polygon)
    participant R as Recipient

    M->>SRC: Burn USDC (via TokenMessenger contract)
    SRC-->>CB: BurnEvent emitted {amount, dest_chain, recipient}
    
    CB->>CB: Attest burn (Circle's attestation API)
    Note over CB: ~13 Ethereum block confirmations (~3min)
    CB-->>M: attestation bytes ready

    M->>DST: Mint USDC (submit attestation to MessageTransmitter)
    DST->>DST: Verify Circle attestation ✓
    DST->>R: Mint USDC to recipient address ✓
    
    Note over SRC,DST: Native USDC — no bridging risk,<br/>no wrapped tokens
```
