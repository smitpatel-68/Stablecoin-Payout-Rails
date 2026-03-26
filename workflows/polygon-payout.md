# Polygon Payout Workflow
## End-to-End USDC Payout on Polygon

---

## Overview

Polygon is the default network for standard payouts. It offers the best balance of cost (~$0.12/tx), speed (~2min finality), and EVM compatibility.

---

## Step-by-Step Flow

### 1. Transaction Construction
- Build USDC ERC-20 `transfer(address,uint256)` calldata
- USDC contract on Polygon: `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` (native USDC via Circle)
- Amount encoded in 6 decimal places (USDC uses 6 decimals, not 18)

### 2. Gas Estimation
- Call `eth_estimateGas` via Alchemy RPC
- Apply 20% buffer to estimated gas to account for network variance
- Check current gas price via `eth_gasPrice` (EIP-1559: base fee + priority fee)
- If total estimated fee > $1.00, log warning (unusual for Polygon)

### 3. Transaction Signing
- Sign with platform custody wallet private key (HSM-backed, never exposed)
- Nonce management: maintain per-wallet nonce counter to prevent stuck transactions
- Set `maxFeePerGas` and `maxPriorityFeePerGas` per EIP-1559

### 4. Broadcast
- Submit signed transaction via Alchemy `eth_sendRawTransaction`
- Receive `tx_hash` immediately
- Store tx_hash → payout_id mapping in ledger

### 5. Confirmation Monitoring
- Poll `eth_getTransactionReceipt` every 5 seconds
- Require 3 block confirmations for finality (~30 seconds after inclusion)
- Parse receipt for:
  - `status`: 1 = success, 0 = revert
  - `gasUsed`: actual gas consumed
  - `effectiveGasPrice`: actual price paid
  - `logs`: USDC Transfer event confirmation

### 6. Failure Handling

| Failure Type | Detection | Action |
|---|---|---|
| Transaction reverts | `status: 0` in receipt | Check revert reason. Common: insufficient USDC balance in custody wallet. Alert ops. |
| Transaction stuck (no receipt after 5min) | Polling timeout | Speed up: resubmit with same nonce + 20% higher gas |
| RPC node down | Connection timeout | Failover to QuickNode backup RPC |
| Nonce conflict | `nonce too low` error | Resync nonce from chain, resubmit |

### 7. Reconciliation
- Extract actual fee: `gasUsed × effectiveGasPrice` → convert to USD
- Record in canonical ledger: payout_id, tx_hash, block_number, fee_usd, settled_at
- Fire `payout.completed` webhook to merchant

---

## Polygon-Specific Considerations

- **Reorgs**: Polygon has occasional 1-block reorgs. 3-confirmation requirement mitigates this.
- **MATIC vs POL**: Polygon migrated gas token from MATIC to POL. Ensure custody wallet holds sufficient POL for gas.
- **USDC versions**: Polygon has both bridged USDC.e and native USDC. We use **native USDC only** (Circle-issued) to avoid bridge risk.
