"""
Agentic Payments Simulator — MPP/x402 Expansion for Tazapay

Demonstrates the three expansion paths:
1. Tazapay as MPP last-mile rail (agent pays via MPP → Tazapay off-ramps to fiat)
2. Tazapay as agent wallet orchestrator (managed wallets with spending policies)
3. Tazapay APIs as MPP-discoverable services (agent discovers and pays per-payout)

Usage:
    python agent_simulator.py --demo     # Run all demo scenarios
    python agent_simulator.py            # Interactive mode
"""

import json
import random
import secrets
import time
import argparse
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional, List

# ─────────────────────────────────────────────
# Protocol Definitions
# ─────────────────────────────────────────────

PROTOCOLS = {
    "mpp": {
        "name": "Machine Payments Protocol (MPP)",
        "provider": "Stripe × Tempo",
        "settlement_chain": "Tempo L1",
        "session_support": True,
        "fee_per_tx": 0.001,
        "finality_ms": 500,
        "supported_methods": ["stablecoin_tempo", "card_stripe", "lightning"],
    },
    "x402": {
        "name": "x402 Protocol",
        "provider": "Coinbase × Cloudflare",
        "settlement_chain": "Base / Polygon / Solana",
        "session_support": True,  # v2
        "fee_per_tx": 0.001,
        "finality_ms": 2000,
        "supported_methods": ["erc20_base", "erc20_polygon", "spl_solana"],
    },
}

# Tazapay off-ramp corridors with costs
CORRIDORS = {
    "USD_INR": {"name": "USD → INR (India)", "fx_spread_pct": 0.30, "settlement_hours": 2, "local_method": "IMPS/UPI"},
    "USD_PHP": {"name": "USD → PHP (Philippines)", "fx_spread_pct": 0.35, "settlement_hours": 4, "local_method": "InstaPay"},
    "USD_VND": {"name": "USD → VND (Vietnam)", "fx_spread_pct": 0.40, "settlement_hours": 6, "local_method": "Napas"},
    "EUR_NGN": {"name": "EUR → NGN (Nigeria)", "fx_spread_pct": 0.50, "settlement_hours": 8, "local_method": "NIP"},
    "USD_IDR": {"name": "USD → IDR (Indonesia)", "fx_spread_pct": 0.35, "settlement_hours": 4, "local_method": "BI-FAST"},
    "USD_MXN": {"name": "USD → MXN (Mexico)", "fx_spread_pct": 0.25, "settlement_hours": 2, "local_method": "SPEI"},
    "USD_BRL": {"name": "USD → BRL (Brazil)", "fx_spread_pct": 0.30, "settlement_hours": 3, "local_method": "PIX"},
}


# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────

@dataclass
class AgentIdentity:
    agent_id: str
    agent_name: str
    owner_merchant: str
    wallet_address: str
    protocol: str  # "mpp" or "x402"


@dataclass
class SpendingPolicy:
    daily_limit_usd: float
    per_tx_limit_usd: float
    allowed_corridors: List[str]
    blocked_wallet_patterns: List[str]
    require_human_approval_above: float
    active_session_id: Optional[str] = None


@dataclass
class MPPSession:
    session_id: str
    agent_id: str
    escrow_amount_usd: float
    spent_usd: float
    remaining_usd: float
    tx_count: int
    created_at: str
    expires_at: str
    status: str  # ACTIVE, EXHAUSTED, EXPIRED


@dataclass
class AgentPayoutRequest:
    agent: AgentIdentity
    amount_usd: float
    currency_in: str  # USDC, USDT
    corridor: str  # e.g., "USD_INR"
    beneficiary_name: str
    beneficiary_account: str
    purpose: str  # e.g., "Supplier payment", "Contractor fee"
    expansion_path: int  # 1, 2, or 3


@dataclass
class AgentPayoutResult:
    payout_id: str
    expansion_path: str
    status: str
    protocol_used: str
    protocol_settlement: dict
    compliance: dict
    off_ramp: dict
    total_cost_usd: float
    total_time_description: str
    decision_rationale: List[str]


# ─────────────────────────────────────────────
# Path 1: Tazapay as MPP/x402 Last-Mile Rail
# ─────────────────────────────────────────────

def simulate_path1_last_mile(request: AgentPayoutRequest) -> AgentPayoutResult:
    """Agent pays via MPP/x402 → Tazapay off-ramps to local fiat."""

    rationale = []
    protocol = PROTOCOLS[request.agent.protocol]
    corridor = CORRIDORS.get(request.corridor)

    if not corridor:
        return _blocked_result(request, f"Corridor {request.corridor} not supported")

    rationale.append(f"Agent {request.agent.agent_name} initiates payment via {protocol['name']}")
    rationale.append(f"Protocol settlement: {protocol['settlement_chain']} ({protocol['finality_ms']}ms finality)")

    # Step 1: Agent pays via protocol
    protocol_fee = protocol["fee_per_tx"]
    rationale.append(f"Agent sends ${request.amount_usd:,.2f} USDC via {request.agent.protocol.upper()} session")
    rationale.append(f"Protocol fee: ${protocol_fee:.4f}")

    # Step 2: Tazapay receives stablecoin and initiates off-ramp
    fx_cost = request.amount_usd * (corridor["fx_spread_pct"] / 100)
    tazapay_fee = 0.50  # flat fee
    total_cost = protocol_fee + fx_cost + tazapay_fee

    rationale.append(f"Tazapay receives USDC on {protocol['settlement_chain']}")
    rationale.append(f"Off-ramp corridor: {corridor['name']}")
    rationale.append(f"FX spread: {corridor['fx_spread_pct']}% (${fx_cost:.2f})")
    rationale.append(f"Tazapay fee: ${tazapay_fee:.2f}")
    rationale.append(f"Local settlement via {corridor['local_method']} — est. {corridor['settlement_hours']}hrs")

    # Compliance
    compliance = _run_compliance(request)
    if compliance["overall"] == "BLOCKED":
        rationale.append("⛔ BLOCKED by compliance screening")
        return AgentPayoutResult(
            payout_id=_gen_id(), expansion_path="Path 1: Last-Mile Rail",
            status="BLOCKED", protocol_used=request.agent.protocol,
            protocol_settlement={}, compliance=compliance, off_ramp={},
            total_cost_usd=0, total_time_description="N/A", decision_rationale=rationale
        )

    return AgentPayoutResult(
        payout_id=_gen_id(),
        expansion_path="Path 1: Last-Mile Rail",
        status="COMPLETED",
        protocol_used=request.agent.protocol,
        protocol_settlement={
            "chain": protocol["settlement_chain"],
            "finality_ms": protocol["finality_ms"],
            "tx_hash": _gen_hash(),
            "fee_usd": protocol_fee,
        },
        compliance=compliance,
        off_ramp={
            "corridor": corridor["name"],
            "fx_spread_pct": corridor["fx_spread_pct"],
            "fx_cost_usd": round(fx_cost, 2),
            "local_method": corridor["local_method"],
            "settlement_hours": corridor["settlement_hours"],
            "tazapay_fee_usd": tazapay_fee,
        },
        total_cost_usd=round(total_cost, 2),
        total_time_description=f"{protocol['finality_ms']}ms protocol + {corridor['settlement_hours']}hrs local settlement",
        decision_rationale=rationale,
    )


# ─────────────────────────────────────────────
# Path 2: Tazapay as Agent Wallet Orchestrator
# ─────────────────────────────────────────────

def simulate_path2_orchestrator(request: AgentPayoutRequest, policy: SpendingPolicy) -> AgentPayoutResult:
    """Managed agent wallet with spending policy enforcement."""

    rationale = []
    corridor = CORRIDORS.get(request.corridor)

    if not corridor:
        return _blocked_result(request, f"Corridor {request.corridor} not supported")

    rationale.append(f"Agent {request.agent.agent_name} (managed by {request.agent.owner_merchant})")
    rationale.append(f"Wallet policy: ${policy.daily_limit_usd:,.0f}/day limit, ${policy.per_tx_limit_usd:,.0f}/tx limit")

    # Step 1: Policy enforcement
    if request.corridor not in policy.allowed_corridors:
        rationale.append(f"⛔ Corridor {request.corridor} not in allowed list: {policy.allowed_corridors}")
        return AgentPayoutResult(
            payout_id=_gen_id(), expansion_path="Path 2: Agent Wallet Orchestrator",
            status="POLICY_BLOCKED", protocol_used="managed_wallet",
            protocol_settlement={}, compliance={}, off_ramp={},
            total_cost_usd=0, total_time_description="N/A", decision_rationale=rationale
        )

    if request.amount_usd > policy.per_tx_limit_usd:
        rationale.append(f"⛔ Amount ${request.amount_usd:,.2f} exceeds per-tx limit ${policy.per_tx_limit_usd:,.0f}")
        return AgentPayoutResult(
            payout_id=_gen_id(), expansion_path="Path 2: Agent Wallet Orchestrator",
            status="POLICY_BLOCKED", protocol_used="managed_wallet",
            protocol_settlement={}, compliance={}, off_ramp={},
            total_cost_usd=0, total_time_description="N/A", decision_rationale=rationale
        )

    if request.amount_usd > policy.require_human_approval_above:
        rationale.append(f"⚠️ Amount ${request.amount_usd:,.2f} exceeds human approval threshold ${policy.require_human_approval_above:,.0f}")
        rationale.append("Payout queued for merchant approval")
        return AgentPayoutResult(
            payout_id=_gen_id(), expansion_path="Path 2: Agent Wallet Orchestrator",
            status="PENDING_HUMAN_APPROVAL", protocol_used="managed_wallet",
            protocol_settlement={}, compliance=_run_compliance(request), off_ramp={},
            total_cost_usd=0, total_time_description="Awaiting merchant approval", decision_rationale=rationale
        )

    rationale.append(f"Policy check: PASSED (amount within limits, corridor allowed)")

    # Step 2: Session management
    session = MPPSession(
        session_id=f"sess_{secrets.token_hex(8)}",
        agent_id=request.agent.agent_id,
        escrow_amount_usd=policy.daily_limit_usd,
        spent_usd=request.amount_usd,
        remaining_usd=policy.daily_limit_usd - request.amount_usd,
        tx_count=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        status="ACTIVE",
    )
    rationale.append(f"MPP session {session.session_id[:20]}... — ${session.remaining_usd:,.2f} remaining")

    # Step 3: Compliance + execution (reuse payout rails logic)
    compliance = _run_compliance(request)
    if compliance["overall"] == "BLOCKED":
        rationale.append("⛔ BLOCKED by compliance screening")
        return AgentPayoutResult(
            payout_id=_gen_id(), expansion_path="Path 2: Agent Wallet Orchestrator",
            status="BLOCKED", protocol_used="managed_wallet",
            protocol_settlement={}, compliance=compliance, off_ramp={},
            total_cost_usd=0, total_time_description="N/A", decision_rationale=rationale
        )

    fx_cost = request.amount_usd * (corridor["fx_spread_pct"] / 100)
    tazapay_fee = 0.50
    total_cost = fx_cost + tazapay_fee

    rationale.append(f"Off-ramp: {corridor['name']} via {corridor['local_method']}")

    return AgentPayoutResult(
        payout_id=_gen_id(),
        expansion_path="Path 2: Agent Wallet Orchestrator",
        status="COMPLETED",
        protocol_used="managed_wallet_mpp",
        protocol_settlement={
            "session_id": session.session_id,
            "session_remaining_usd": session.remaining_usd,
            "session_tx_count": session.tx_count,
        },
        compliance=compliance,
        off_ramp={
            "corridor": corridor["name"],
            "fx_spread_pct": corridor["fx_spread_pct"],
            "fx_cost_usd": round(fx_cost, 2),
            "local_method": corridor["local_method"],
            "settlement_hours": corridor["settlement_hours"],
            "tazapay_fee_usd": tazapay_fee,
        },
        total_cost_usd=round(total_cost, 2),
        total_time_description=f"Instant session debit + {corridor['settlement_hours']}hrs local settlement",
        decision_rationale=rationale,
    )


# ─────────────────────────────────────────────
# Path 3: Tazapay APIs as MPP-Discoverable Service
# ─────────────────────────────────────────────

def simulate_path3_discovery(request: AgentPayoutRequest) -> AgentPayoutResult:
    """Agent discovers Tazapay in MPP directory and pays per-payout."""

    rationale = []
    protocol = PROTOCOLS[request.agent.protocol]
    corridor = CORRIDORS.get(request.corridor)

    if not corridor:
        return _blocked_result(request, f"Corridor {request.corridor} not supported")

    # Step 1: Discovery
    rationale.append(f"Agent queries MPP directory for 'cross-border fiat payout'")
    rationale.append(f"Discovers: Tazapay Payout Service — {len(CORRIDORS)} corridors available")
    rationale.append(f"No signup required. Pay-per-payout pricing.")

    # Step 2: 402 Challenge
    per_payout_fee = 0.50
    fx_spread = corridor["fx_spread_pct"]
    total_estimated = per_payout_fee + (request.amount_usd * fx_spread / 100)

    rationale.append(f"HTTP 402 challenge received:")
    rationale.append(f"  Price: ${per_payout_fee:.2f} + {fx_spread}% FX spread = ${total_estimated:.2f} estimated")
    rationale.append(f"  Methods accepted: stablecoin (Tempo), card (Stripe)")

    # Step 3: Agent pays and retries
    protocol_fee = protocol["fee_per_tx"]
    rationale.append(f"Agent pays ${total_estimated:.2f} via {protocol['name']}")
    rationale.append(f"Retries request with payment credential")

    # Step 4: Compliance + execution
    compliance = _run_compliance(request)
    if compliance["overall"] == "BLOCKED":
        rationale.append("⛔ BLOCKED — refund issued to agent wallet")
        return AgentPayoutResult(
            payout_id=_gen_id(), expansion_path="Path 3: MPP-Discoverable Service",
            status="BLOCKED_REFUNDED", protocol_used=request.agent.protocol,
            protocol_settlement={}, compliance=compliance, off_ramp={},
            total_cost_usd=0, total_time_description="N/A", decision_rationale=rationale
        )

    # Step 5: Instant onboarding check
    rationale.append(f"Agent wallet first seen — instant onboarding (no KYB for <$1,000/day)")
    rationale.append(f"Payout executing: {corridor['name']} via {corridor['local_method']}")

    fx_cost = request.amount_usd * (fx_spread / 100)
    total_cost = protocol_fee + per_payout_fee + fx_cost

    return AgentPayoutResult(
        payout_id=_gen_id(),
        expansion_path="Path 3: MPP-Discoverable Service",
        status="COMPLETED",
        protocol_used=request.agent.protocol,
        protocol_settlement={
            "discovery": "MPP Payments Directory",
            "challenge": f"HTTP 402 — ${total_estimated:.2f}",
            "chain": protocol["settlement_chain"],
            "tx_hash": _gen_hash(),
        },
        compliance=compliance,
        off_ramp={
            "corridor": corridor["name"],
            "fx_spread_pct": fx_spread,
            "fx_cost_usd": round(fx_cost, 2),
            "local_method": corridor["local_method"],
            "settlement_hours": corridor["settlement_hours"],
            "per_payout_fee": per_payout_fee,
            "onboarding": "instant (no KYB required)",
        },
        total_cost_usd=round(total_cost, 2),
        total_time_description=f"Discovery + {protocol['finality_ms']}ms payment + {corridor['settlement_hours']}hrs local",
        decision_rationale=rationale,
    )


# ─────────────────────────────────────────────
# Shared Utilities
# ─────────────────────────────────────────────

def _run_compliance(request):
    SANCTIONED = ["0xSanctionedWallet001", "SANCTIONED_ACCT"]
    if request.beneficiary_account in SANCTIONED:
        return {"sanctions": "FAIL", "kyt_score": 100, "overall": "BLOCKED"}
    score = random.randint(0, 30)
    travel_rule = request.amount_usd >= 3000
    return {
        "sanctions": "PASS",
        "kyt_score": score,
        "kyt_verdict": "LOW",
        "travel_rule_triggered": travel_rule,
        "travel_rule_action": "ENHANCED_MONITORING" if travel_rule and request.amount_usd < 10000 else ("SELF_CERT" if travel_rule else "NONE"),
        "overall": "CLEARED",
    }

_ID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _gen_id():
    # Use `secrets` for identifiers — `random` is not a CSPRNG. Simulated risk
    # scoring below intentionally keeps `random` because it's non-security.
    return f"po_{''.join(secrets.choice(_ID_ALPHABET) for _ in range(12))}"


def _gen_hash():
    return f"0x{secrets.token_hex(32)}"

def _blocked_result(request, reason):
    return AgentPayoutResult(
        payout_id=_gen_id(), expansion_path="N/A",
        status="BLOCKED", protocol_used=request.agent.protocol,
        protocol_settlement={}, compliance={"reason": reason}, off_ramp={},
        total_cost_usd=0, total_time_description="N/A", decision_rationale=[f"⛔ {reason}"]
    )


# ─────────────────────────────────────────────
# Output Formatting
# ─────────────────────────────────────────────

def print_result(request: AgentPayoutRequest, result: AgentPayoutResult):
    print("\n" + "=" * 72)
    print(f"  {result.expansion_path}")
    print(f"  PAYOUT: {result.payout_id}")
    print("=" * 72)

    print(f"\n  Agent:          {request.agent.agent_name} ({request.agent.agent_id[:16]}...)")
    print(f"  Owner:          {request.agent.owner_merchant}")
    print(f"  Protocol:       {request.agent.protocol.upper()}")
    print(f"  Amount:         ${request.amount_usd:,.2f} {request.currency_in}")
    print(f"  Corridor:       {request.corridor}")
    print(f"  Beneficiary:    {request.beneficiary_name}")
    print(f"  Purpose:        {request.purpose}")

    print(f"\n  Compliance:")
    for k, v in result.compliance.items():
        print(f"    {k}: {v}")

    print(f"\n  Decision Rationale:")
    for step in result.decision_rationale:
        print(f"    → {step}")

    if result.status in ("BLOCKED", "BLOCKED_REFUNDED", "POLICY_BLOCKED", "PENDING_HUMAN_APPROVAL"):
        print(f"\n  Status: ⛔ {result.status}")
    else:
        print(f"\n  Protocol Settlement:")
        for k, v in result.protocol_settlement.items():
            print(f"    {k}: {v}")
        print(f"\n  Off-Ramp:")
        for k, v in result.off_ramp.items():
            print(f"    {k}: {v}")
        print(f"\n  Total Cost:     ${result.total_cost_usd:.2f}")
        print(f"  Total Time:     {result.total_time_description}")
        print(f"  Status:         ✅ {result.status}")

    print("=" * 72)


# ─────────────────────────────────────────────
# Demo Scenarios
# ─────────────────────────────────────────────

def run_demo():
    print("\n🤖 AGENTIC PAYMENTS SIMULATOR — Tazapay Expansion Paths")
    print("=" * 72)
    print(f"  Simulating MPP/x402 integration scenarios...")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # ── PATH 1 SCENARIOS ──

    print("\n\n" + "─" * 72)
    print("  PATH 1: TAZAPAY AS MPP/x402 LAST-MILE RAIL")
    print("─" * 72)

    # 1a: Agent pays supplier in Philippines via MPP
    req1a = AgentPayoutRequest(
        agent=AgentIdentity("agent_proc_001", "ProcurementBot-7", "AcmeCorp US", "0xAgentWallet001", "mpp"),
        amount_usd=4200, currency_in="USDC", corridor="USD_PHP",
        beneficiary_name="Manila Supplies Co", beneficiary_account="PH_BANK_12345",
        purpose="Supplier payment — Q1 fabric order", expansion_path=1,
    )
    print_result(req1a, simulate_path1_last_mile(req1a))

    # 1b: Agent pays contractor in India via x402
    req1b = AgentPayoutRequest(
        agent=AgentIdentity("agent_hr_002", "TalentPayBot", "TechStartup EU", "0xAgentWallet002", "x402"),
        amount_usd=1500, currency_in="USDC", corridor="USD_INR",
        beneficiary_name="Priya Sharma", beneficiary_account="IN_UPI_priya@upi",
        purpose="Contractor fee — March development sprint", expansion_path=1,
    )
    print_result(req1b, simulate_path1_last_mile(req1b))

    # ── PATH 2 SCENARIOS ──

    print("\n\n" + "─" * 72)
    print("  PATH 2: TAZAPAY AS AGENT WALLET ORCHESTRATOR")
    print("─" * 72)

    merchant_policy = SpendingPolicy(
        daily_limit_usd=10000, per_tx_limit_usd=5000,
        allowed_corridors=["USD_INR", "USD_PHP", "USD_VND", "USD_IDR"],
        blocked_wallet_patterns=["0xSanctioned"],
        require_human_approval_above=3000,
    )

    # 2a: Agent within policy limits
    req2a = AgentPayoutRequest(
        agent=AgentIdentity("agent_ops_003", "SupplyChainBot", "GlobalMarketplace", "0xManagedWallet003", "mpp"),
        amount_usd=800, currency_in="USDC", corridor="USD_VND",
        beneficiary_name="Hanoi Manufacturing Ltd", beneficiary_account="VN_BANK_67890",
        purpose="Component order — batch #447", expansion_path=2,
    )
    print_result(req2a, simulate_path2_orchestrator(req2a, merchant_policy))

    # 2b: Agent exceeds human approval threshold
    req2b = AgentPayoutRequest(
        agent=AgentIdentity("agent_ops_003", "SupplyChainBot", "GlobalMarketplace", "0xManagedWallet003", "mpp"),
        amount_usd=4500, currency_in="USDC", corridor="USD_PHP",
        beneficiary_name="Cebu Electronics Supplier", beneficiary_account="PH_BANK_99999",
        purpose="Large component order — requires approval", expansion_path=2,
    )
    print_result(req2b, simulate_path2_orchestrator(req2b, merchant_policy))

    # 2c: Agent tries blocked corridor
    req2c = AgentPayoutRequest(
        agent=AgentIdentity("agent_ops_003", "SupplyChainBot", "GlobalMarketplace", "0xManagedWallet003", "mpp"),
        amount_usd=2000, currency_in="USDC", corridor="EUR_NGN",
        beneficiary_name="Lagos Trading Co", beneficiary_account="NG_BANK_11111",
        purpose="Attempted payment to non-allowed corridor", expansion_path=2,
    )
    print_result(req2c, simulate_path2_orchestrator(req2c, merchant_policy))

    # ── PATH 3 SCENARIOS ──

    print("\n\n" + "─" * 72)
    print("  PATH 3: TAZAPAY APIs AS MPP-DISCOVERABLE SERVICE")
    print("─" * 72)

    # 3a: New agent discovers Tazapay, pays per-payout
    req3a = AgentPayoutRequest(
        agent=AgentIdentity("agent_new_004", "KenyaOpsBot", "SmallBiz Kenya", "0xNewAgentWallet", "mpp"),
        amount_usd=350, currency_in="USDC", corridor="USD_MXN",
        beneficiary_name="Artesanias MX", beneficiary_account="MX_CLABE_123456",
        purpose="Product sourcing — first-time supplier", expansion_path=3,
    )
    print_result(req3a, simulate_path3_discovery(req3a))

    # 3b: Agent discovers via x402
    req3b = AgentPayoutRequest(
        agent=AgentIdentity("agent_fin_005", "TreasuryBot", "CryptoNative Inc", "0xCryptoAgent", "x402"),
        amount_usd=8000, currency_in="USDC", corridor="USD_BRL",
        beneficiary_name="SaoPaulo Dev Studio", beneficiary_account="BR_PIX_dev@studio",
        purpose="Development milestone payment", expansion_path=3,
    )
    print_result(req3b, simulate_path3_discovery(req3b))

    # ── EDGE CASES ──

    print("\n\n" + "─" * 72)
    print("  EDGE CASES: OFF-RAMP FAILURES")
    print("─" * 72)

    # 4a: Bank rejection on off-ramp
    req4a = AgentPayoutRequest(
        agent=AgentIdentity("agent_proc_001", "ProcurementBot-7", "AcmeCorp US", "0xAgentWallet001", "mpp"),
        amount_usd=3200, currency_in="USDC", corridor="USD_IDR",
        beneficiary_name="Jakarta Parts Co", beneficiary_account="INVALID_BANK_ACCT",
        purpose="Supplier payment — bank details mismatch", expansion_path=1,
    )
    # Simulate bank rejection
    result_4a = simulate_path1_last_mile(req4a)
    if result_4a.status == "COMPLETED":
        result_4a.status = "OFF_RAMP_FAILED"
        result_4a.decision_rationale.append("⚠️ Local bank rejected: beneficiary account validation failed")
        result_4a.decision_rationale.append("USDC held in custody — merchant notified to update beneficiary details")
        result_4a.decision_rationale.append("Auto-refund to merchant stablecoin balance after 72hr hold")
    print_result(req4a, result_4a)

    # 4b: FX rate slippage between agent payment and fiat settlement
    req4b = AgentPayoutRequest(
        agent=AgentIdentity("agent_fin_005", "TreasuryBot", "CryptoNative Inc", "0xCryptoAgent", "mpp"),
        amount_usd=25000, currency_in="USDC", corridor="USD_BRL",
        beneficiary_name="SaoPaulo Manufacturing", beneficiary_account="BR_PIX_mfg@corp",
        purpose="Large payment — FX rate moved during settlement", expansion_path=1,
    )
    result_4b = simulate_path1_last_mile(req4b)
    if result_4b.status == "COMPLETED":
        # Simulate FX slippage
        original_fx = result_4b.off_ramp.get("fx_cost_usd", 0)
        slippage = round(req4b.amount_usd * 0.0015, 2)  # 0.15% adverse move
        result_4b.off_ramp["fx_slippage_usd"] = slippage
        result_4b.off_ramp["fx_note"] = "BRL weakened 0.15% between quote and settlement"
        result_4b.total_cost_usd = round(result_4b.total_cost_usd + slippage, 2)
        result_4b.decision_rationale.append(f"⚠️ FX slippage: BRL moved 0.15% adverse — additional ${slippage:.2f} cost absorbed by platform")
        result_4b.decision_rationale.append("Mitigation: FX rate locked for 30s at quote time. Slippage beyond lock window absorbed up to 0.25%, passed to merchant above that.")
    print_result(req4b, result_4b)

    # ── SUMMARY ──

    print("\n\n" + "=" * 72)
    print("  SUMMARY — AGENTIC EXPANSION SIMULATION")
    print("=" * 72)
    print(f"\n  Path 1 (Last-Mile Rail):        2 scenarios — agent pays via MPP/x402, Tazapay off-ramps")
    print(f"  Path 2 (Wallet Orchestrator):    3 scenarios — managed wallets with spending policies")
    print(f"  Path 3 (Discoverable Service):   2 scenarios — agents find Tazapay in MPP directory")
    print(f"  Edge Cases:                      2 scenarios — bank rejection + FX slippage")
    print(f"\n  Protocols demonstrated:          MPP (Stripe/Tempo), x402 (Coinbase)")
    print(f"  Corridors used:                  PHP, INR, VND, MXN, BRL, IDR, NGN (blocked)")
    print(f"  Compliance paths:                CLEARED, Travel Rule, Policy Blocked, Human Approval")
    print(f"  Failure paths:                   Off-ramp rejection, FX slippage")
    print("=" * 72)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agentic Payments Expansion Simulator")
    parser.add_argument("--demo", action="store_true", help="Run demo scenarios")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        print("Interactive mode coming soon. Use --demo for now.")
