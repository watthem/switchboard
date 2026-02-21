# Switchboard — Architecture Overview

**Stage:** Pre-validation (Gate 1 pending)
**Last updated:** 2026-02-18

---

## Problem

AI agents are easy to run and hard to govern. Every team builds agents in their own stack — Python, Ruby, Go, TypeScript, custom frameworks. There is no standard way to answer three questions that every security team asks before approving deployment:

1. **What can this agent access?** (least-privilege)
2. **What did this agent do?** (audit trail)
3. **Who authorized it?** (accountability)

Today's answers are "everything," "we don't know," and "nobody." Switchboard fixes this without requiring teams to rewrite their agents or adopt a new runtime.

## Core Principle

**Switchboard manages the box, not the code inside it.**

Like Kubernetes doesn't care if your service is written in Go, Java, or Python — it manages the container — Switchboard doesn't care how your agent is built. It manages the *boundary*: what the agent can access, what events it emits, and what policy governs it.

The interface between Switchboard and any agent is a contract at the infrastructure level, not a language-specific SDK or schema standard.

## The Switchboard Protocol

Switchboard defines a minimal contract between any agent and the Switchboard control plane. The contract has three parts:

### 1. Policy In (Switchboard → Agent)

Switchboard writes a policy file that the agent's runtime reads. The format adapts to the runtime — JSON, YAML, TOML, environment variables. The content is the same:

```yaml
# Example: policy.yaml (written by Switchboard sidecar)
agent_id: warehouse-monitor
tier: L2
allowed_actions:
  - read_inventory
  - update_stock_level
  - send_alert
denied_actions:
  - delete_records
  - access_credentials
rate_limit:
  external_api_calls_per_minute: 10
channels:
  - inventory-alerts
  - warehouse-ops
```

The agent reads this however its runtime prefers. A Python agent reads YAML. A Ruby agent reads JSON. A Go binary reads env vars. Switchboard doesn't care.

### 2. Events Out (Agent → Switchboard)

The agent emits structured events to a known HTTP endpoint. Five fields:

```json
{
  "agent_id": "warehouse-monitor",
  "timestamp": "2026-02-18T14:32:01Z",
  "action": "update_stock_level",
  "target": "inventory.sku.A1234",
  "result": "success"
}
```

Any language can do this in three lines of code. This is the audit trail.

### 3. Enforcement Layer (Infrastructure)

Hard security boundaries that don't depend on agent cooperation:

- **Container mounts** — An L0 agent has no write mounts. Period.
- **Network policies** — An L1 agent can reach Switchboard and nothing else.
- **Credential injection** — Secrets live in Switchboard, not in agent containers.
- **Resource limits** — CPU, memory, and API rate caps at the container level.

This layer works regardless of what the agent does internally. A compromised agent is trapped in its box.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Control Plane                     │
│    (Fleet dashboard, policy editor, audit log)    │
│              [Rails / Web UI]                     │
└────────────────────┬────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────┐
│                   Switchboard                          │
│            (Protocol endpoint)                    │
│  • Ingests events from any agent                  │
│  • Distributes policy to agent sidecars           │
│  • Enforces rate limits and access control         │
│  • Stores audit trail                             │
└──┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │
┌──▼──┐  ┌───▼──┐  ┌───▼──┐  ┌───▼──┐
│Scar │  │Scar  │  │Scar  │  │Scar  │
│     │  │      │  │      │  │      │
│Agent│  │Agent │  │Agent │  │Agent │
│(Py) │  │(Ruby)│  │(Go)  │  │(any) │
│     │  │      │  │      │  │      │
│ L0  │  │ L1   │  │ L2   │  │ L3   │
└─────┘  └──────┘  └──────┘  └──────┘
Docker    Docker    Docker    Docker
```

Each agent runs with a **sidecar** — a thin process that handles the Switchboard protocol on the agent's behalf. The sidecar:
- Pulls policy from Switchboard and writes it in the format the agent expects
- Forwards the agent's event output to Switchboard
- Reports health status (heartbeat)

The sidecar is ~50 lines of code in any language. Pre-built sidecars ship for Python, Ruby, and Go. Writing one for a new language takes a day.

## Autonomy Tiers (L0–L3)

| Tier | Label | What the Agent Can Do | Enforcement |
|------|-------|-----------------------|-------------|
| L0 | Observer | Read-only, no network, no writes | Container has no write mounts or network access |
| L1 | Assistant | Read data via Switchboard | Switchboard enforces read-only routing |
| L2 | Operator | Read/write within scope | Human-in-the-loop gate on write actions |
| L3 | Autonomous | Full action within policy boundary | Policy-bounded, audit-logged |

Tiers are enforced at the container and network level — not by prompts. An L0 agent physically cannot write to the filesystem because its Docker container has no write mounts. The model's intentions are irrelevant.

## How to Add a New Agent

Regardless of what runtime or language the agent uses:

1. **Deploy with sidecar** — Run your agent container alongside the Switchboard sidecar. The sidecar connects to Switchboard automatically.
2. **Set tier** — Choose L0–L3 from the control plane UI or API. Container mounts and network policy are configured accordingly.
3. **Emit events** — Have your agent POST structured events to the sidecar's local endpoint. Five fields: agent_id, timestamp, action, target, result.
4. **Read policy** — Your agent reads its policy from a local file the sidecar maintains. Format is whatever your runtime prefers.

That's it. No framework to adopt, no schema to conform to, no language requirement.

## Threat Model

| Vector | Containment |
|--------|-------------|
| **Prompt injection** | Compromised model is trapped in its container. An L0 agent that gets injected still has no write mounts and no network. Damage ceiling is zero. |
| **Credential exfiltration** | Secrets live in Switchboard, not in agent containers. Agents receive processed data only. No agent can read another agent's environment. |
| **Lateral movement** | No direct agent-to-agent communication. All messages route through Switchboard. A compromised agent cannot discover or reach other agents. |
| **Rogue sidecar** | The sidecar runs as a separate process with its own auth token. Even if an agent compromises its sidecar, container-level enforcement (mounts, network) still holds. |

## What This Is Not

Switchboard is not a model safety tool. It does not evaluate prompt quality, detect hallucinations, or filter model outputs. It enforces infrastructure-level access control — what an agent *can do*, regardless of what the model *wants to do*.

Switchboard is not an agent framework. It does not prescribe how agents are built, what language they use, or what schema they prefer. It manages the boundary around agents that already exist.

## Reference Implementation

The `switchboard/` directory contains the first Switchboard implementation (FastAPI/Python). The `agents/` directory contains working agent configurations using OpenClaw as the runtime. This is the prototype that proves the architecture — not the only way to deploy.
