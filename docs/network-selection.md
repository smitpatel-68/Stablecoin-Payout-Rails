# Network Selection Logic
## Multi-Chain Routing for Stablecoin Payouts

---

## Decision Tree

When a merchant submits a payout with `network: auto`, the platform evaluates the following in order:

### 1. Merchant Override
If the merchant specifies a network (`polygon`, `solana`, `ethereum`), we use it directly. No further evaluation. This exists for merchants with specific compliance requirements or existing wallet infrastructure on a particular chain.

### 2. Amount-Based Routing

| Amount | Network | Rationale |
|---|---|---|
| > $100,000 | Ethereum | Highest settlement security. Institutional trust. Lower relative gas cost at this amount. |
| $500 – $100,000 | Polygon (default) | Best cost/speed balance. ~2min finality, $0.01–0.15 fees. |
| < $500 | Polygon or Tron | Polygon default. Tron if USDT-only and gas is elevated. |

### 3. Volume-Based Routing

| Merchant Daily Volume | Network | Rationale |
|---|---|---|
| > 500 tx/day | Solana | 400ms finality, $0.00025/tx. Cost savings compound at volume. |
| ≤ 500 tx/day | Polygon | Standard default. |

### 4. Gas-Aware Fallback

| Condition | Action |
|---|---|
| Polygon gas < 500 gwei | Proceed on Polygon |
| Polygon gas ≥ 500 gwei | Check if Tron fallback enabled |
| Tron enabled + USDT | Route to Tron ($0.10/tx) |
| Tron not enabled | Queue and retry in 10 minutes |

---

## Gas Oracle Integration

The network selector checks real-time gas prices before every routing decision:

- **Polygon**: EIP-1559 gas estimation via Alchemy `eth_gasPrice`
- **Ethereum**: EIP-1559 base fee + priority fee via Alchemy
- **Solana**: Compute unit pricing via Helius `getRecentPrioritizationFees`

Gas prices are cached for 15 seconds to avoid excessive RPC calls during burst payout periods.

---

## Override Behavior

Merchants can force a specific network via the `network` parameter in the API request. When overriding:

- The platform still performs full compliance screening (sanctions, KYT, Travel Rule)
- Wallet address format is validated against the specified chain (EVM for Polygon/Ethereum, base58 for Solana)
- If the specified network is unavailable (RPC down), the payout is queued — not auto-routed to a different chain
- Override decisions are logged separately for audit purposes

---

## Future Considerations

- **Base (Coinbase L2)**: Likely Phase 4 addition. Low fees, strong USDC ecosystem, growing institutional adoption.
- **Arbitrum**: EVM-compatible, lower gas than Ethereum mainnet. Candidate for mid-range amounts ($50K–$100K).
- **Dynamic routing**: ML-based model that learns optimal routing from historical cost/speed/success data per corridor.
