# Operational Runbook

Response procedures for the common failure modes of the stablecoin payout
platform. Each section is a standalone playbook that an on-call engineer
can follow from a cold start at 03:00.

The alert thresholds referenced here are defined in `docs/metrics.md`.

---

## 0. Before you start

1. Join `#payouts-oncall` in Slack. Acknowledge the page.
2. Open the ops dashboard (`dash.internal/payouts`).
3. Open the incident document template: `runbooks/template.md`.
4. Assume nothing about the state — **verify every claim** with a command
   from this document.

If at any point you need to **halt all payouts**, use the kill-switch:

```
$ payout-cli halt --reason "<free text>" --duration 15m
```

This flips the platform into maintenance mode: in-flight payouts continue,
new submissions receive `503 Service Unavailable` with `Retry-After: 900`.
The kill-switch requires two-person approval (you + any other on-call).

---

## 1. Payout success rate < 95% for 15 minutes (P1)

**Alert:** `payout_success_rate_15m < 0.95`

### Triage
1. Check the ops dashboard breakdown: which status is dominating the
   failure column?
2. Check if failures are concentrated on one network: `payout_cli status
   --group-by network`.
3. Check if failures are concentrated on one merchant: `payout_cli status
   --group-by merchant_id`.

### Likely causes

| Symptom | Go to |
|---|---|
| Failures concentrated on Polygon, low gas balance on custody wallet | §6 Custody wallet low balance |
| Failures concentrated on one chain, RPC timeouts in logs | §2 RPC primary + failover down |
| Failures concentrated on one merchant, many compliance flags | §4 Compliance vendor outage |
| Failures across all networks, 5xx on internal services | §7 Internal service outage |
| Failures all show status `PAUSED_DEPEG` | §5 Stablecoin depeg |

### If unclear
Halt new payouts with the kill-switch (§0), then page the platform lead.
The cost of a 15-minute halt is low; the cost of draining the float during
an incident is high.

---

## 2. RPC primary + failover down for a chain (P1)

**Alert:** `rpc_availability{network="polygon"} == 0` (or solana / ethereum)

### Triage
1. Confirm from a second vantage point: `curl -sS -o /dev/null -w "%{http_code}\n" $PRIMARY_RPC/health` and same for failover.
2. Check the RPC provider status pages (Alchemy, Helius, QuickNode, Triton).
3. Check if failures are mentioned on `status.<provider>.com`.

### Actions
1. **Do not** route traffic manually to a third RPC unless that RPC has
   been pre-validated by the infra team (fake-response risk — see threat
   model T6).
2. The network selector will automatically route away from the affected
   chain after 3 consecutive failures in 5 minutes — confirm this happened
   by tailing `rpc-failover.log`.
3. If the affected chain is Polygon (the default), merchant traffic will
   spill to Solana or Ethereum. Watch `custody_balance{network="solana"}`
   and `custody_balance{network="ethereum"}` for draw-down.
4. If the outage exceeds 15 minutes:
   - Notify affected merchants via status page.
   - If outage exceeds 2 hours, escalate to platform lead and consider
     activating Tron fallback for opt-in USDT merchants (see
     `docs/compliance.md` §5).
5. When the chain is healthy again, do **not** force-drain the retry queue
   — let the scheduled retry pick it up naturally to avoid a thundering
   herd.

### Comms
If customer-visible: update `status.yourcompany.com` within 5 minutes of
confirming. If cross-chain fallback absorbed the outage silently, still
file a post-incident report within 24 hours.

---

## 3. Sanctions list refresh failure (P2 escalating to P1)

**Alert:** `sanctions_list_age > 5 hours`

### Background
Sanctions screening is **fail-closed**: if the list is stale, every payout
is hard-blocked at the compliance layer. This is the correct posture for
regulatory compliance but it halts revenue.

### Triage
1. Confirm the list source (OFAC SDN, UN, EU) — check each independently:
   `payout-cli compliance sanctions-age`.
2. Check the fetcher logs: `kubectl logs -n compliance sanctions-fetcher`.
3. Check if the upstream source itself is down (OFAC's hosted file).

### Actions
1. If the upstream is down: document the exception in the compliance
   journal. Do **not** override the hard block without explicit written
   approval from the compliance officer.
2. If the fetcher is down: restart it. `kubectl rollout restart deployment
   sanctions-fetcher -n compliance`.
3. If the list hash verification failed (tampering detected): **stop, do
   not refresh from that source**, and escalate to the compliance officer
   and security team immediately. This is a S5 threat — see threat model.
4. Once resolved, run `payout-cli compliance reconcile` to retroactively
   screen any payouts that were blocked during the outage and process the
   ones that pass.

### Do not
- Do not cache a previous list beyond 5 hours "to keep things moving".
- Do not manually edit the sanctions list file.
- Do not skip the compliance layer for any merchant, no matter how loud
  they get.

---

## 4. Compliance vendor outage (P2)

**Alert:** `chainalysis_unreachable` or `notabene_unreachable`

### Background
Both KYT (Chainalysis) and Travel Rule (Notabene) are fail-closed. The
platform will issue `503 Service Unavailable` on new payouts with
`Retry-After` set to the expected outage duration.

### Triage
1. Confirm the outage against the vendor status page.
2. Confirm our outbound path isn't the problem: `curl -v
   https://api.chainalysis.com/health` from a core service pod.
3. Check the vendor incident response SLA in the contract (under
   `contracts/compliance/`).

### Actions
1. If the outage is expected to be short (< 30m): let the fail-closed
   behaviour run. Update the status page.
2. If the outage will be longer:
   - Switch to the standby vendor if the contract permits
     (see `contracts/compliance/secondary.md`).
   - If no standby: document the exception and leave payouts halted.
3. Do not lower the KYT / Travel Rule bar to unblock revenue. This is a
   hard constraint from legal.

---

## 5. Stablecoin depeg (P1)

**Alert:** `stablecoin_deviation_pct > 0.5`

### Background
The depeg threshold is 0.5% deviation from USD. At that point, all payouts
in the affected stablecoin are auto-paused (see
`simulator/payout_simulator.py` depeg logic).

### Triage
1. Confirm the depeg against a second price source (Chainlink, CoinGecko,
   DEX TWAP).
2. Check which stablecoin is depegged — USDC and USDT are handled
   independently.
3. Check the issuer's status page and Twitter.

### Actions
1. Pause affected payouts — this is automatic but confirm via
   `payout-cli status --filter status=PAUSED_DEPEG`.
2. Notify affected merchants with a status page update and a targeted
   email to merchants with pending payouts in the depegged stablecoin.
3. If an on-ramp alternative is available (USDC for a USDT depeg, or vice
   versa), offer merchants a one-click switch via the dashboard.
4. Do **not** resume payouts automatically when the peg recovers — wait
   for 30 consecutive minutes within the healthy band, then manually
   resume after compliance sign-off.

---

## 6. Custody wallet low balance (P2)

**Alert:** `custody_balance_hours < 48`

### Triage
1. Which chain, which token: the alert label has both.
2. Check the last rebalance time: `payout-cli rebalance history`.
3. Check whether CCTP is healthy: `payout-cli cctp status`.

### Actions
1. Trigger a rebalance via CCTP: `payout-cli rebalance --network=<x>
   --token=<y> --amount=<z>`. This burns USDC on the source chain and
   mints on the destination chain via Circle's attestation.
2. If CCTP is down, initiate a manual treasury transfer (requires
   finance approval). Document in the incident report.
3. If the burn rate is unusually high, investigate whether a single
   merchant is spiking — may indicate a compromised merchant key (see §8).

### Prevention
The rebalancer should catch this before the alert fires. If it didn't,
file a follow-up ticket to tighten the auto-rebalance threshold.

---

## 7. Internal service outage (P1)

**Alert:** `http_5xx_rate > 0.01` on any core service

### Triage
1. Which service? Ops dashboard shows per-service error rate.
2. Is this a deploy-related regression? Check the deploy timeline.
3. Is it traffic-driven? Check the RPS graph.

### Actions
1. If a deploy was the trigger: roll back. `payout-cli deploy rollback
   <service>`. Rollback is strictly safer than fixing forward under
   incident conditions.
2. If traffic-driven: scale the affected service and, if the spike comes
   from a single merchant, apply per-merchant rate limiting via
   `payout-cli ratelimit set --merchant=<x> --rpm=<y>`.
3. Never roll back the execution engine without draining in-flight
   payouts first — it holds non-idempotent state around nonces.

---

## 8. Suspected merchant key compromise (P1)

**Trigger:** Anomaly detection flags a merchant OR the merchant reports
key exfiltration.

### Actions
1. **Revoke the key immediately.** `payout-cli key revoke --merchant=<x>
   --key=<prefix>`. This takes effect within 30 seconds across the edge.
2. Invalidate all in-flight idempotency keys for that merchant.
3. Freeze the merchant's payout queue: `payout-cli merchant freeze
   --merchant=<x>`. In-flight payouts continue, new submissions return
   `403 Forbidden` until the freeze is lifted.
4. Pull the last 24h of requests signed with the revoked key:
   `payout-cli audit --key=<prefix> --since=24h`. Flag any that look
   unusual (new beneficiaries, unusual corridors, amounts near limits).
5. Escalate to the compliance officer and the merchant's account manager.
6. The merchant must rotate their signing secret and webhook secret
   before the freeze is lifted.

---

## 9. Reorg on a "completed" payout (P1)

**Alert:** `reorg_after_completion` (custom detector)

### Background
Polygon has occasional 1-block reorgs. Our confirmation depth (3 on
Polygon, 12+ on Ethereum scaled to amount) makes this rare but not
impossible — especially at shallow confirmation on Ethereum.

### Actions
1. Confirm the reorg independently: query the failover RPC for the same
   block range.
2. Flip the payout status from `COMPLETED` to `FAILED` with reason
   `REORG_DETECTED`. This is one of very few allowed backward transitions
   — see `diagrams/flows.md` §6.
3. Trigger an automatic refund flow to the merchant's balance (the funds
   never left the custody wallet because the burn was reverted).
4. Notify the merchant via webhook — a new `payout.reorged` event.
5. File a post-incident report including amount, chain, reorg depth, and
   the confirmation policy that was in effect.

### If the amount was > $100K
Escalate to compliance immediately. Large reorgs may trigger regulator
reporting depending on the jurisdiction.

---

## 10. Kill-switch triggered (P1)

**Trigger:** Manual (§0) or automatic on:

- Custody wallet balance below safety floor on all chains
- Detection of a signed payout without a matching authorization from the
  execution engine (E3 threat)
- Compliance list integrity failure (S5 threat)

### Recovery
1. Investigate and resolve the root cause.
2. Require two-person approval to lift the switch: `payout-cli resume
   --approved-by=<a> --approved-by=<b>`.
3. Drain the queued 503 requests gradually — do not open the floodgates.
4. File a post-incident report within 24 hours.

---

## 11. Post-incident

Every P1 triggers a post-incident report within 3 business days. The
template lives at `runbooks/template.md` and must include:

1. Timeline (timestamps in UTC).
2. Detection path (alert → page → ack).
3. Root cause.
4. Blast radius (merchants affected, payouts halted, funds at risk).
5. What worked.
6. What didn't.
7. Follow-up actions with owners and due dates.

Follow-up actions are tracked in the `post-incident` label on GitHub and
reviewed at the weekly platform sync.
