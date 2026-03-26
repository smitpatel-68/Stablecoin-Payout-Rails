# Multi-Chain Network Topology

```mermaid
graph TB
    subgraph Platform Infrastructure
        CW[Custody Wallets]
        EE[Execution Engine]
        NS[Network Selector]
    end

    subgraph Polygon Infra
        PA[Alchemy RPC — Primary]
        PB[QuickNode RPC — Failover]
        PC[USDC Contract<br/>0x3c499c542cEF5E38...]
        PP[POL Gas Token]
    end

    subgraph Solana Infra
        SA[Helius RPC — Primary]
        SB[Triton RPC — Failover]
        SC[USDC SPL Token<br/>EPjFWdd5AufqSSqe...]
        SS[SOL Gas Token]
    end

    subgraph Ethereum Infra
        EA[Alchemy RPC — Primary]
        EB[QuickNode RPC — Failover]
        EC[USDC Contract<br/>0xA0b86991c6218b36...]
        EG[ETH Gas Token]
    end

    subgraph Circle Infrastructure
        CCTP[CCTP — Cross-Chain Transfer Protocol]
        ATT[Circle Attestation API]
    end

    NS --> EE
    EE --> CW

    CW -->|Polygon txns| PA
    PA -.->|failover| PB
    PA --> PC
    PP -->|gas| PA

    CW -->|Solana txns| SA
    SA -.->|failover| SB
    SA --> SC
    SS -->|gas| SA

    CW -->|Ethereum txns| EA
    EA -.->|failover| EB
    EA --> EC
    EG -->|gas| EA

    PC <-->|burn/mint| CCTP
    EC <-->|burn/mint| CCTP
    SC <-->|burn/mint| CCTP
    CCTP --> ATT
```

## Custody Wallet Architecture

| Network | Wallet Type | Gas Token | USDC Type |
|---|---|---|---|
| Polygon | EVM EOA (HSM-backed) | POL | Native USDC (Circle) |
| Solana | Ed25519 keypair (HSM-backed) | SOL | SPL USDC (Circle) |
| Ethereum | EVM EOA (HSM-backed) | ETH | Native USDC (Circle) |

Each network has a dedicated custody wallet. Wallets are funded with:
- Sufficient stablecoin balance for expected daily payout volume + 20% buffer
- Gas token balance for estimated daily transactions + 50% buffer

Gas token balances are monitored. Alerts fire when balance drops below 48 hours of estimated gas consumption.

## RPC Failover Strategy

Each network uses a primary + failover RPC provider:

1. All requests go to primary provider
2. If primary returns error or times out (>5s), retry on failover
3. If both fail, payout is queued in dead letter with `NETWORK_UNAVAILABLE` status
4. Ops alerted. Payout retried automatically every 10 minutes for 2 hours.
5. After 2 hours, escalated to manual resolution.

## Circle CCTP

Circle's Cross-Chain Transfer Protocol enables native USDC movement between chains without bridging risk:

- **Burn on source chain** → Circle attests the burn → **Mint on destination chain**
- No wrapped tokens. Native USDC on both sides.
- Used when platform needs to rebalance custody wallet USDC across chains
- Not used for individual payouts (each payout executes on a single chain)
