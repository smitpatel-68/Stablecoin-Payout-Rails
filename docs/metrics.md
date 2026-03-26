# Success Metrics & Instrumentation
## KPIs, Dashboards, and Monitoring

---

## North Star Metric

**Payout Success Rate** — % of initiated payouts that reach `COMPLETED` status without manual intervention.

Target: > 99% (Phase 1), > 99.5% (Phase 3)

---

## Primary Metrics

| Metric | Definition | Target | Instrumentation |
|---|---|---|---|
| Payout Success Rate | Completed / Total initiated | > 99% | API status tracking |
| Avg Settlement Time | API submission → on-chain confirmation | < 3min (Polygon), < 1min (Solana) | Timestamp diff: created_at to settled_at |
| Avg Fee Per Transaction | Blended across all networks | < $0.50 | Gas fee logging per tx |
| Compliance Screening Latency | Time for sanctions + KYT + travel rule | < 5s p99 | Per-check timestamps |

## Secondary Metrics

| Metric | Definition | Target | Why It Matters |
|---|---|---|---|
| Developer Integration Time | API key issued → first successful payout | < 2.5 days | DX quality signal |
| KYT False Positive Rate | Medium/High flags on legitimate wallets | < 5% | Ops burden + merchant friction |
| API Error Rate | 4xx + 5xx / total requests | < 0.5% | Platform reliability |
| Webhook Delivery Rate | Successful webhook deliveries / total attempts | > 99.5% | Merchant reconciliation depends on this |
| Network Selection Override Rate | Merchant-specified network / total payouts | Track only | Indicates if auto-routing is trusted |

## Operational Metrics

| Metric | Definition | Alert Threshold |
|---|---|---|
| RPC Node Availability | Uptime per network (Alchemy, Helius) | < 99.9% → alert |
| Gas Price Anomaly | Polygon gas > 500 gwei sustained > 10min | Trigger Tron fallback |
| Dead Letter Queue Depth | Unresolved payouts in DLQ | > 10 → page ops |
| Sanctions List Freshness | Time since last OFAC/UN/EU refresh | > 5 hours → hard block all payouts |
| Compliance Review Backlog | Flagged payouts awaiting review | > 20 → alert compliance team |

---

## Dashboard Design

### Merchant-Facing Dashboard

Merchants see:
- Real-time payout status (QUEUED → SCREENING → EXECUTING → CONFIRMING → COMPLETED)
- Settlement time distribution (histogram, last 30 days)
- Fee summary by network
- Compliance flags and resolutions
- Daily/weekly/monthly payout volume and value

### Internal Ops Dashboard

Operations team sees:
- Live payout pipeline (in-flight transactions by network)
- Compliance screening queue (flagged payouts awaiting review)
- Network health (RPC uptime, gas prices, confirmation times)
- Dead letter queue with manual resolution interface
- Reconciliation discrepancies (on-chain vs ledger mismatches)

---

## Alerting

| Severity | Condition | Channel | Response SLA |
|---|---|---|---|
| P1 (Critical) | Payout success rate < 95% for 15min | PagerDuty + Slack | 15 min |
| P1 (Critical) | Any network RPC fully down | PagerDuty + Slack | 15 min |
| P2 (High) | KYT provider (Chainalysis) unreachable | Slack | 1 hour |
| P2 (High) | Sanctions list refresh failed | Slack + hard block | 1 hour |
| P3 (Medium) | Gas spike causing Tron fallback | Slack | Monitor |
| P3 (Medium) | Webhook delivery failures > 5% | Slack | 4 hours |
