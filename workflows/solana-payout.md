# Solana Payout Workflow
## USDC Payouts on Solana — High-Volume Merchants

---

## Overview

Solana is activated for merchants with daily volume > 500 tx/day. It offers 400ms finality and ~$0.00025/tx — making it the most cost-efficient option at scale.

---

## Key Differences from EVM Chains

| Aspect | Polygon/Ethereum | Solana |
|---|---|---|
| Token standard | ERC-20 | SPL Token |
| Address format | 0x... (hex, 42 chars) | Base58 (32-44 chars) |
| USDC decimals | 6 | 6 |
| Finality | ~2min (Polygon), ~3min (Eth) | ~400ms |
| Fee model | Gas (gwei) | Compute units + priority fee |
| Account model | Account/balance | Account/rent |

---

## Step-by-Step Flow

### 1. Pre-checks
- Validate beneficiary address is valid base58
- Check if beneficiary has an existing USDC Associated Token Account (ATA)
- If no ATA exists: the platform creates it (costs ~0.002 SOL in rent)

### 2. Transaction Construction
- Use `@solana/spl-token` SDK: `createTransferInstruction`
- Source: platform custody token account
- Destination: beneficiary's ATA
- Amount: value × 10^6 (USDC has 6 decimals on Solana too)

### 3. Fee Estimation
- Query `getRecentPrioritizationFees` via Helius
- Set compute unit limit and priority fee
- Total fee typically: $0.00020 – $0.00050

### 4. Signing & Broadcast
- Sign with platform custody wallet keypair (stored in HSM)
- Submit via `sendTransaction` (Helius RPC)
- Receive transaction signature immediately

### 5. Confirmation
- Poll `getSignatureStatuses` every 1 second
- Solana transactions are finalized in ~400ms after inclusion
- Check `confirmationStatus`: `processed` → `confirmed` → `finalized`
- We require `finalized` status before marking complete

### 6. Failure Handling

| Failure Type | Detection | Action |
|---|---|---|
| Transaction dropped | Not found after 30s | Resubmit with fresh blockhash |
| Insufficient SOL for rent | Simulation error | Top up custody wallet SOL balance |
| RPC congestion | Timeout on send | Failover to Triton backup RPC |
| Blockhash expired | Error on submit | Fetch new blockhash, re-sign, resubmit |

---

## Solana-Specific Considerations

- **ATA creation cost**: If the beneficiary doesn't have a USDC token account, we create one. This adds ~$0.002 to the transaction cost. We absorb this — merchants shouldn't see variable fees.
- **Durable nonces**: For high-value Solana payouts, we use durable nonces instead of recent blockhashes to prevent expiry during compliance screening delays.
- **Circle USDC on Solana**: We use Circle's native USDC SPL token (mint: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`). No bridged/wrapped versions.
- **Network congestion**: Solana occasionally experiences congestion where transaction inclusion slows. Priority fees mitigate this, and we fall back to Polygon if Solana inclusion exceeds 30 seconds.
