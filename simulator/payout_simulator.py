"""
Stablecoin Payout Rails — Network Selection Simulator

Simulates the multi-chain routing logic for USDC/USDT payouts.
Takes payment parameters as input and outputs:
- Selected network (Polygon, Solana, Ethereum)
- Estimated fee and settlement time
- Compliance screening result
- Full decision rationale

Usage:
    python payout_simulator.py                    # Interactive mode
    python payout_simulator.py --demo             # Run demo scenarios
"""

import json
import random
import secrets
import time
import argparse
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from typing import Optional

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

NETWORKS = {
    "polygon": {
        "name": "Polygon",
        "avg_finality_seconds": 120,
        "base_fee_usd": 0.12,
        "max_gas_gwei_threshold": 500,
        "supported_tokens": ["USDC", "USDT"],
        "rpc_provider": "Alchemy",
    },
    "solana": {
        "name": "Solana",
        "avg_finality_seconds": 2,
        "base_fee_usd": 0.00025,
        "max_gas_gwei_threshold": None,
        "supported_tokens": ["USDC"],
        "rpc_provider": "Helius",
    },
    "ethereum": {
        "name": "Ethereum",
        "avg_finality_seconds": 180,
        "base_fee_usd": 4.50,
        "max_gas_gwei_threshold": 200,
        "supported_tokens": ["USDC", "USDT"],
        "rpc_provider": "Alchemy",
    },
    "tron": {
        "name": "Tron (fallback)",
        "avg_finality_seconds": 6,
        "base_fee_usd": 0.10,
        "max_gas_gwei_threshold": None,
        "supported_tokens": ["USDT"],
        "rpc_provider": "TronGrid",
    },
}

SANCTIONS_LIST = [
    "0xSanctionedWallet001",
    "0xSanctionedWallet002",
    "0xOFACBlockedAddress",
]

HIGH_RISK_WALLETS = [
    "0xHighRiskMixer001",
    "0xDarknetMarket002",
]

# Stablecoin peg health (simulated — in production, fetched from DEX price feeds)
PEG_STATUS = {
    "USDC": {"price_usd": 1.0000, "deviation_pct": 0.00, "status": "HEALTHY"},
    "USDT": {"price_usd": 0.9998, "deviation_pct": 0.02, "status": "HEALTHY"},
}

# Depeg threshold — if deviation exceeds this, all payouts in that stablecoin are paused
DEPEG_THRESHOLD_PCT = 0.50


# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────

@dataclass
class PayoutRequest:
    amount_usd: float
    currency: str  # USDC or USDT
    beneficiary_wallet: str
    beneficiary_name: str
    network: str  # "auto" or specific network
    merchant_daily_volume: int  # tx count today
    # Merchant must explicitly opt in to Tron fallback — see docs/compliance.md §5.
    # When False, gas-spike conditions queue for retry instead of routing to Tron.
    tron_fallback_enabled: bool = False
    metadata: Optional[dict] = None


@dataclass
class ComplianceResult:
    sanctions_check: str  # PASS, FAIL
    kyt_risk_score: int  # 0-100
    kyt_verdict: str  # LOW, MEDIUM, HIGH
    travel_rule_triggered: bool
    travel_rule_action: str  # NONE, IVMS_101_SENT, ENHANCED_MONITORING, SELF_CERT_REQUIRED
    overall: str  # CLEARED, FLAGGED, BLOCKED


@dataclass
class NetworkDecision:
    selected_network: str
    rationale: list  # list of reasoning steps
    estimated_fee_usd: float
    estimated_settlement_seconds: int
    alternatives: list  # other networks considered


@dataclass
class PayoutResult:
    payout_id: str
    status: str
    compliance: ComplianceResult
    network_decision: NetworkDecision
    tx_hash: Optional[str]
    settled_at: Optional[str]
    total_time_seconds: float


# ─────────────────────────────────────────────
# Compliance Engine
# ─────────────────────────────────────────────

def screen_compliance(request: PayoutRequest) -> ComplianceResult:
    """Screen beneficiary wallet for sanctions, AML risk, and travel rule."""

    # Sanctions check
    if request.beneficiary_wallet in SANCTIONS_LIST:
        return ComplianceResult(
            sanctions_check="FAIL",
            kyt_risk_score=100,
            kyt_verdict="HIGH",
            travel_rule_triggered=False,
            travel_rule_action="NONE",
            overall="BLOCKED",
        )

    # KYT risk scoring (simulated)
    if request.beneficiary_wallet in HIGH_RISK_WALLETS:
        risk_score = random.randint(75, 95)
    else:
        risk_score = random.randint(0, 35)

    if risk_score >= 75:
        kyt_verdict = "HIGH"
        overall = "BLOCKED"
    elif risk_score >= 40:
        kyt_verdict = "MEDIUM"
        overall = "FLAGGED"
    else:
        kyt_verdict = "LOW"
        overall = "CLEARED"

    # Travel rule (FATF: transfers >= $3,000)
    travel_rule_triggered = request.amount_usd >= 3000
    if travel_rule_triggered:
        if request.amount_usd >= 10000:
            travel_rule_action = "SELF_CERT_REQUIRED"
        else:
            travel_rule_action = "ENHANCED_MONITORING"
    else:
        travel_rule_action = "NONE"

    return ComplianceResult(
        sanctions_check="PASS",
        kyt_risk_score=risk_score,
        kyt_verdict=kyt_verdict,
        travel_rule_triggered=travel_rule_triggered,
        travel_rule_action=travel_rule_action,
        overall=overall,
    )


# ─────────────────────────────────────────────
# Network Selector
# ─────────────────────────────────────────────

def select_network(request: PayoutRequest) -> NetworkDecision:
    """Select optimal blockchain network based on amount, volume, gas, and token."""

    rationale = []
    current_gas = {
        "polygon": random.randint(80, 400),
        "ethereum": random.randint(20, 150),
    }

    # If merchant specified a network
    if request.network != "auto":
        net = NETWORKS.get(request.network)
        if net:
            rationale.append(f"Merchant explicitly requested {net['name']}")
            return NetworkDecision(
                selected_network=request.network,
                rationale=rationale,
                estimated_fee_usd=net["base_fee_usd"],
                estimated_settlement_seconds=net["avg_finality_seconds"],
                alternatives=[],
            )

    # Decision tree for auto selection
    # Step 1: Large amounts → Ethereum
    if request.amount_usd > 100_000:
        rationale.append(f"Amount ${request.amount_usd:,.2f} > $100K threshold")
        rationale.append("Ethereum selected for highest security guarantees")
        return NetworkDecision(
            selected_network="ethereum",
            rationale=rationale,
            estimated_fee_usd=NETWORKS["ethereum"]["base_fee_usd"],
            estimated_settlement_seconds=NETWORKS["ethereum"]["avg_finality_seconds"],
            alternatives=[
                {"network": "polygon", "fee": 0.12, "reason": "Lower security for this amount"},
            ],
        )

    # Step 2: High daily volume → Solana
    if request.merchant_daily_volume > 500 and request.currency == "USDC":
        rationale.append(f"Merchant daily volume: {request.merchant_daily_volume} tx > 500 threshold")
        rationale.append("Solana selected for throughput and near-zero fees")
        return NetworkDecision(
            selected_network="solana",
            rationale=rationale,
            estimated_fee_usd=NETWORKS["solana"]["base_fee_usd"],
            estimated_settlement_seconds=NETWORKS["solana"]["avg_finality_seconds"],
            alternatives=[
                {"network": "polygon", "fee": 0.12, "reason": "Viable but higher per-tx cost at volume"},
            ],
        )

    # Step 3: Check Polygon gas
    polygon_gas = current_gas["polygon"]
    if polygon_gas < 500:
        rationale.append(f"Amount ${request.amount_usd:,.2f} within standard range")
        rationale.append(f"Polygon gas: {polygon_gas} gwei (< 500 threshold)")
        rationale.append("Polygon selected as default — best cost/speed balance")
        return NetworkDecision(
            selected_network="polygon",
            rationale=rationale,
            estimated_fee_usd=NETWORKS["polygon"]["base_fee_usd"],
            estimated_settlement_seconds=NETWORKS["polygon"]["avg_finality_seconds"],
            alternatives=[
                {"network": "solana", "fee": 0.00025, "reason": "Faster but USDC-only"},
                {"network": "ethereum", "fee": 4.50, "reason": "Higher security, much higher cost"},
            ],
        )

    # Step 4: Polygon gas spike → Tron fallback. USDT only AND merchant must
    # have opted in (see docs/network-selection.md and docs/compliance.md §5).
    rationale.append(f"Polygon gas spike: {polygon_gas} gwei (>= 500 threshold)")
    if request.currency == "USDT" and request.tron_fallback_enabled:
        rationale.append("Tron fallback selected — USDT only, merchant opted in, near-zero fees")
        return NetworkDecision(
            selected_network="tron",
            rationale=rationale,
            estimated_fee_usd=NETWORKS["tron"]["base_fee_usd"],
            estimated_settlement_seconds=NETWORKS["tron"]["avg_finality_seconds"],
            alternatives=[
                {"network": "polygon", "fee": 0.12, "reason": "Available after gas normalizes"},
            ],
        )

    # Step 5: Gas elevated, Tron unavailable (not USDT, or merchant opted out).
    # Production would queue for 10-min retry per docs/network-selection.md;
    # the simulator proceeds on Polygon to keep the demo flow finite.
    rationale.append("Tron fallback unavailable (currency != USDT or merchant opt-out)")
    rationale.append("Proceeding on Polygon (production: queue for 10min retry)")
    return NetworkDecision(
        selected_network="polygon",
        rationale=rationale,
        estimated_fee_usd=NETWORKS["polygon"]["base_fee_usd"],
        estimated_settlement_seconds=NETWORKS["polygon"]["avg_finality_seconds"],
        alternatives=[],
    )


# ─────────────────────────────────────────────
# Execution Simulator
# ─────────────────────────────────────────────

def simulate_execution(network: str) -> tuple:
    """Simulate transaction execution. Returns (tx_hash, settlement_time_seconds)."""
    net = NETWORKS[network]
    # Use `secrets` for identifier / hash generation. `random` is a Mersenne
    # Twister and is not suitable for anything that *looks* like a production
    # transaction hash — readers shouldn't copy that pattern into real code.
    tx_hash = f"0x{secrets.token_hex(32)}"
    # `random.randint` is fine here: simulated settlement jitter is not
    # security-relevant.
    settlement = net["avg_finality_seconds"] + random.randint(-10, 30)
    settlement = max(1, settlement)
    return tx_hash, settlement


# ─────────────────────────────────────────────
# Main Payout Flow
# ─────────────────────────────────────────────

def process_payout(request: PayoutRequest) -> PayoutResult:
    """Full payout pipeline: depeg check → compliance → network selection → execution."""

    start = time.time()
    # Use `secrets` for the payout ID — see simulate_execution() note.
    _id_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    payout_id = f"po_{''.join(secrets.choice(_id_alphabet) for _ in range(12))}"

    # Step 0: Peg health check
    peg = PEG_STATUS.get(request.currency, {})
    if peg.get("deviation_pct", 0) >= DEPEG_THRESHOLD_PCT:
        return PayoutResult(
            payout_id=payout_id,
            status="PAUSED_DEPEG",
            compliance=ComplianceResult("N/A", 0, "N/A", False, "NONE", "PAUSED"),
            network_decision=NetworkDecision("none", [
                f"{request.currency} peg deviation: {peg['deviation_pct']:.2f}% (threshold: {DEPEG_THRESHOLD_PCT}%)",
                f"Current price: ${peg['price_usd']:.4f}",
                "All payouts in this stablecoin paused. Fallback to fiat if available.",
            ], 0, 0, []),
            tx_hash=None,
            settled_at=None,
            total_time_seconds=time.time() - start,
        )

    # Step 1: Compliance screening
    compliance = screen_compliance(request)

    if compliance.overall == "BLOCKED":
        return PayoutResult(
            payout_id=payout_id,
            status="BLOCKED",
            compliance=compliance,
            network_decision=NetworkDecision("none", ["Blocked by compliance"], 0, 0, []),
            tx_hash=None,
            settled_at=None,
            total_time_seconds=time.time() - start,
        )

    if compliance.overall == "FLAGGED":
        return PayoutResult(
            payout_id=payout_id,
            status="FLAGGED_FOR_REVIEW",
            compliance=compliance,
            network_decision=NetworkDecision("pending", ["Awaiting compliance review (4hr SLA)"], 0, 0, []),
            tx_hash=None,
            settled_at=None,
            total_time_seconds=time.time() - start,
        )

    # Step 2: Network selection
    network_decision = select_network(request)

    # Step 3: Execution
    tx_hash, settlement_seconds = simulate_execution(network_decision.selected_network)
    settled_at = (datetime.now(timezone.utc) + timedelta(seconds=settlement_seconds)).isoformat() + "Z"

    return PayoutResult(
        payout_id=payout_id,
        status="COMPLETED",
        compliance=compliance,
        network_decision=network_decision,
        tx_hash=tx_hash,
        settled_at=settled_at,
        total_time_seconds=time.time() - start,
    )


# ─────────────────────────────────────────────
# Output Formatting
# ─────────────────────────────────────────────

def print_result(request: PayoutRequest, result: PayoutResult):
    """Pretty-print a payout result."""
    print("\n" + "=" * 70)
    print(f"  PAYOUT: {result.payout_id}")
    print("=" * 70)

    print(f"\n  Request:")
    print(f"    Amount:       ${request.amount_usd:,.2f} {request.currency}")
    print(f"    Beneficiary:  {request.beneficiary_name}")
    print(f"    Wallet:       {request.beneficiary_wallet[:20]}...")
    print(f"    Network pref: {request.network}")
    print(f"    Merchant vol: {request.merchant_daily_volume} tx/day")

    print(f"\n  Compliance:")
    print(f"    Sanctions:    {result.compliance.sanctions_check}")
    print(f"    KYT Score:    {result.compliance.kyt_risk_score} ({result.compliance.kyt_verdict})")
    print(f"    Travel Rule:  {'Triggered' if result.compliance.travel_rule_triggered else 'Not triggered'}")
    if result.compliance.travel_rule_triggered:
        print(f"    TR Action:    {result.compliance.travel_rule_action}")
    print(f"    Overall:      {result.compliance.overall}")

    if result.status in ("BLOCKED", "FLAGGED_FOR_REVIEW", "PAUSED_DEPEG"):
        print(f"\n  Status: ⛔ {result.status}")
        if result.status == "PAUSED_DEPEG":
            print(f"\n  Depeg Rationale:")
            for step in result.network_decision.rationale:
                print(f"    → {step}")
        print("=" * 70)
        return

    print(f"\n  Network Decision:")
    print(f"    Selected:     {result.network_decision.selected_network.upper()}")
    print(f"    Fee:          ${result.network_decision.estimated_fee_usd:.4f}")
    print(f"    Est. settle:  {result.network_decision.estimated_settlement_seconds}s")
    print(f"    Rationale:")
    for step in result.network_decision.rationale:
        print(f"      → {step}")

    print(f"\n  Execution:")
    print(f"    Status:       ✅ {result.status}")
    print(f"    Tx Hash:      {result.tx_hash[:30]}...")
    print(f"    Settled at:   {result.settled_at}")

    if result.network_decision.alternatives:
        print(f"\n  Alternatives Considered:")
        for alt in result.network_decision.alternatives:
            print(f"    • {alt['network'].upper()} (${alt['fee']:.4f}) — {alt['reason']}")

    print("=" * 70)


# ─────────────────────────────────────────────
# Demo Scenarios
# ─────────────────────────────────────────────

DEMO_SCENARIOS = [
    {
        "name": "Standard payout — Philippines contractor",
        "request": PayoutRequest(
            amount_usd=4200,
            currency="USDC",
            beneficiary_wallet="0x7a3B9c2D4e5F6A8b1C0d2E3f4A5B6c7D8E9f0A1b",
            beneficiary_name="Acme Supplies PH",
            network="auto",
            merchant_daily_volume=300,
        ),
    },
    {
        "name": "Large enterprise wire — $250K to Singapore",
        "request": PayoutRequest(
            amount_usd=250000,
            currency="USDC",
            beneficiary_wallet="0x1a2B3c4D5e6F7a8B9c0D1e2F3a4B5c6D7e8F9a0B",
            beneficiary_name="TechCorp Singapore Pte Ltd",
            network="auto",
            merchant_daily_volume=50,
        ),
    },
    {
        "name": "High-volume marketplace — 800 tx/day",
        "request": PayoutRequest(
            amount_usd=150,
            currency="USDC",
            beneficiary_wallet="0x9f8E7d6C5b4A3f2E1d0C9b8A7f6E5d4C3b2A1f0E",
            beneficiary_name="Freelancer XYZ",
            network="auto",
            merchant_daily_volume=800,
        ),
    },
    {
        "name": "Sanctioned wallet — should be blocked",
        "request": PayoutRequest(
            amount_usd=1000,
            currency="USDT",
            beneficiary_wallet="0xSanctionedWallet001",
            beneficiary_name="Unknown Entity",
            network="auto",
            merchant_daily_volume=100,
        ),
    },
    {
        "name": "Travel Rule — $8K to unhosted wallet",
        "request": PayoutRequest(
            amount_usd=8000,
            currency="USDC",
            beneficiary_wallet="0xAa1Bb2Cc3Dd4Ee5Ff6Aa7Bb8Cc9Dd0Ee1Ff2Aa3Bb4",
            beneficiary_name="Supplier MEA Ltd",
            network="auto",
            merchant_daily_volume=200,
        ),
    },
    {
        "name": "Travel Rule — $15K requires self-certification",
        "request": PayoutRequest(
            amount_usd=15000,
            currency="USDC",
            beneficiary_wallet="0xFf1Ee2Dd3Cc4Bb5Aa6Ff7Ee8Dd9Cc0Bb1Aa2Ff3Ee4",
            beneficiary_name="Manufacturing Co LatAm",
            network="auto",
            merchant_daily_volume=120,
        ),
    },
    {
        "name": "Merchant forces Solana",
        "request": PayoutRequest(
            amount_usd=500,
            currency="USDC",
            beneficiary_wallet="SoLaNaWaLLeTaDdReSs1234567890abcdefghijk",
            beneficiary_name="Contractor Brazil",
            network="solana",
            merchant_daily_volume=50,
        ),
    },
    {
        "name": "Stablecoin depeg event — USDT deviates >0.5%",
        "request": PayoutRequest(
            amount_usd=2000,
            currency="USDT",
            beneficiary_wallet="0xBb2Cc3Dd4Ee5Ff6Aa7Bb8Cc9Dd0Ee1Ff2Aa3Bb4Cc",
            beneficiary_name="SEA Vendor Ltd",
            network="auto",
            merchant_daily_volume=200,
        ),
        "depeg_override": {"USDT": {"price_usd": 0.9940, "deviation_pct": 0.60, "status": "DEPEGGED"}},
    },
]


def run_demo():
    """Run all demo scenarios and print results."""
    print("\n" + "🌐 STABLECOIN PAYOUT RAILS — SIMULATOR")
    print("=" * 70)
    print(f"  Running {len(DEMO_SCENARIOS)} demo scenarios...")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}Z")

    results = []
    for scenario in DEMO_SCENARIOS:
        print(f"\n\n📋 Scenario: {scenario['name']}")

        # Apply depeg override if specified in scenario
        original_peg = {}
        if "depeg_override" in scenario:
            for token, peg_data in scenario["depeg_override"].items():
                original_peg[token] = PEG_STATUS.get(token, {}).copy()
                PEG_STATUS[token] = peg_data

        result = process_payout(scenario["request"])
        print_result(scenario["request"], result)
        results.append({"scenario": scenario["name"], "result": asdict(result)})

        # Restore original peg status
        for token, peg_data in original_peg.items():
            PEG_STATUS[token] = peg_data

    # Summary
    completed = sum(1 for r in results if r["result"]["status"] == "COMPLETED")
    blocked = sum(1 for r in results if r["result"]["status"] == "BLOCKED")
    flagged = sum(1 for r in results if r["result"]["status"] == "FLAGGED_FOR_REVIEW")
    depegged = sum(1 for r in results if r["result"]["status"] == "PAUSED_DEPEG")

    print("\n\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Total payouts:  {len(results)}")
    print(f"  Completed:      {completed}")
    print(f"  Blocked:        {blocked}")
    print(f"  Flagged:        {flagged}")
    print(f"  Paused (depeg): {depegged}")

    networks_used = {}
    for r in results:
        net = r["result"]["network_decision"]["selected_network"]
        if net not in ("none", "pending"):
            networks_used[net] = networks_used.get(net, 0) + 1
    print(f"\n  Networks used:")
    for net, count in networks_used.items():
        print(f"    {net.upper()}: {count} payouts")

    print("=" * 70)

    # Export JSON
    with open("simulation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results exported to simulation_results.json\n")


def interactive_mode():
    """Interactive single payout mode."""
    print("\n🌐 STABLECOIN PAYOUT RAILS — Interactive Mode\n")

    amount = float(input("  Amount (USD): "))
    currency = input("  Currency (USDC/USDT) [USDC]: ").strip().upper() or "USDC"
    wallet = input("  Beneficiary wallet: ").strip() or "0xDefaultWallet123456789"
    name = input("  Beneficiary name: ").strip() or "Unknown"
    network = input("  Network (auto/polygon/solana/ethereum) [auto]: ").strip().lower() or "auto"
    volume = int(input("  Merchant daily tx volume [100]: ").strip() or "100")

    request = PayoutRequest(
        amount_usd=amount,
        currency=currency,
        beneficiary_wallet=wallet,
        beneficiary_name=name,
        network=network,
        merchant_daily_volume=volume,
    )

    result = process_payout(request)
    print_result(request, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stablecoin Payout Rails Simulator")
    parser.add_argument("--demo", action="store_true", help="Run demo scenarios")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        interactive_mode()
