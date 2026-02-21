# Protected Actions & Approvals

Switchboard controls what agents can and cannot do through policy-defined action lists and tier-level enforcement.

---

## How Actions Work

Every event an agent emits has an `action` field — a string describing what the agent did:

```json
{
  "agent_id": "my-agent",
  "action": "file_write",
  "target": "/data/report.csv",
  "result": "success"
}
```

Switchboard's policy system controls which actions are allowed:

```json
{
  "allowed_actions": ["file_read", "api_call", "send_alert"],
  "denied_actions": ["delete_records", "access_credentials"]
}
```

## Allowed vs. Denied Actions

| Field | Behavior |
|-------|----------|
| `allowed_actions` | Whitelist. If non-empty, only these actions are permitted. |
| `denied_actions` | Blacklist. These actions are always blocked, even if in the allowed list. |

If both lists are empty, the agent can perform any action within its tier constraints.

## Rate Limits

Every agent has configurable rate limits:

```json
{
  "rate_limits": {
    "events_per_minute": 60,
    "external_api_calls_per_minute": 10
  }
}
```

## Tier-Level Enforcement

Action policy works alongside [tier enforcement](autonomy-tiers.md):

- **L0** agents have no write mounts — `file_write` physically cannot succeed
- **L1** agents have no external network — `api_call` to outside services is blocked at the network level
- **L2** agents route write actions through a human-in-the-loop gate
- **L3** agents execute within policy bounds, all actions audit-logged

## Updating Policy

```bash
curl -X PUT http://localhost:59237/api/v1/agents/my-agent/policy \
  -H "Content-Type: application/json" \
  -H "X-Switchboard-Key: $SWITCHBOARD_API_KEY" \
  -d '{
    "allowed_actions": ["file_read", "file_write"],
    "denied_actions": ["delete_records"],
    "rate_limits": {"events_per_minute": 30}
  }'
```

Policy updates increment the version number. The sidecar picks up the new policy on its next sync cycle.
