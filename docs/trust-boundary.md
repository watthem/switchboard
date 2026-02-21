# The Trust Boundary

Switchboard manages the box, not the code inside it.

---

## The Problem

AI agents are easy to run and hard to govern. Every team builds agents in their own stack — Python, Ruby, Go, TypeScript, custom frameworks. There is no standard way to answer three questions that every security team asks before approving deployment:

1. **What can this agent access?** (least-privilege)
2. **What did this agent do?** (audit trail)
3. **Who authorized it?** (accountability)

Today's answers are "everything," "we don't know," and "nobody."

## Switchboard's Approach

Like Kubernetes doesn't care if your service is written in Go, Java, or Python — it manages the container — Switchboard doesn't care how your agent is built. It manages the **boundary**: what the agent can access, what events it emits, and what policy governs it.

The interface between Switchboard and any agent is a contract at the infrastructure level, not a language-specific SDK or schema standard.

## What This Means in Practice

| Vector | Without Switchboard | With Switchboard |
|--------|---------------|-------------|
| **Prompt injection** | Compromised model has whatever access the developer gave it | Compromised model is trapped in its container. An L0 agent that gets injected still has no write mounts and no network. |
| **Credential exfiltration** | Secrets live in agent env vars | Secrets live in Switchboard, not in agent containers. Agents receive processed data only. |
| **Lateral movement** | Agents can discover and call other services | No direct agent-to-agent communication. All messages route through Switchboard. |
| **Rogue sidecar** | No sidecar exists | Even if compromised, container-level enforcement (mounts, network) still holds. |

## What Switchboard Is Not

Switchboard is **not a model safety tool**. It does not evaluate prompt quality, detect hallucinations, or filter model outputs. It enforces infrastructure-level access control — what an agent *can do*, regardless of what the model *wants to do*.

Switchboard is **not an agent framework**. It does not prescribe how agents are built, what language they use, or what schema they prefer. It manages the boundary around agents that already exist.
