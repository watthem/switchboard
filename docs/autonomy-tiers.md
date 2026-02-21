# Autonomy Tiers (L0-L3)

Switchboard governs agent capabilities through four autonomy tiers, enforced at the infrastructure level.

---

## Tier Overview

| Tier | Label | What the Agent Can Do | Enforcement |
|------|-------|-----------------------|-------------|
| **L0** | Observer | Read-only, no network, no writes | Container has no write mounts or network access |
| **L1** | Assistant | Read data via Switchboard | Switchboard enforces read-only routing |
| **L2** | Operator | Read/write within scope | Human-in-the-loop gate on write actions |
| **L3** | Autonomous | Full action within policy boundary | Policy-bounded, audit-logged |

## Key Principle

Tiers are enforced at the **container and network level** — not by prompts. An L0 agent physically cannot write to the filesystem because its Docker container has no write mounts. The model's intentions are irrelevant.

## L0 — Observer

The most restrictive tier. The agent can observe but cannot act.

- **Filesystem:** Read-only mounts only
- **Network:** No outbound access (except Switchboard via sidecar)
- **Use cases:** Monitoring, log analysis, read-only dashboards
- **Risk ceiling:** Zero. Even a fully compromised L0 agent cannot cause damage.

## L1 — Assistant

The agent can read data and respond to queries, but cannot modify state.

- **Filesystem:** Read-only mounts
- **Network:** Switchboard API only (via sidecar)
- **Use cases:** Q&A bots, research assistants, data lookups
- **Risk ceiling:** Information disclosure only. No state changes possible.

## L2 — Operator

The agent can read and write within a defined scope, with human approval on writes.

- **Filesystem:** Scoped read/write mounts
- **Network:** Allowed endpoints only (configured in policy)
- **HITL gate:** Write actions require human-in-the-loop approval
- **Use cases:** Code assistants, content editors, automated ops with approval
- **Risk ceiling:** Scoped to approved write targets. Human reviews every mutation.

## L3 — Autonomous

Full action authority within the policy boundary. No human gate on individual actions.

- **Filesystem:** Full access within policy scope
- **Network:** All allowed endpoints
- **Audit:** Every action logged to Switchboard
- **Use cases:** CI/CD automation, autonomous ops, scheduled tasks
- **Risk ceiling:** Bounded by policy. Every action is auditable. Revocable at any time.

## Setting a Tier

### Via API

```bash
curl -X PUT http://localhost:59237/api/v1/agents/my-agent/policy \
  -H "Content-Type: application/json" \
  -H "X-Switchboard-Key: $SWITCHBOARD_API_KEY" \
  -d '{"tier": "L2"}'
```

### At Registration

```bash
curl -X POST http://localhost:59237/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "X-Switchboard-Key: $SWITCHBOARD_API_KEY" \
  -d '{"agent_id": "my-agent", "tier": "L1"}'
```

### Via Dashboard

Open the [dashboard](http://localhost:59237/dashboard), select an agent, and use the tier selector.

## Tier Escalation

Tiers can be changed at any time by an admin. The sidecar picks up the new policy on its next sync cycle (default: 30 seconds). There is no automatic tier escalation — an agent cannot promote itself.
