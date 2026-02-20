# API Reference

Herald v1 governance protocol endpoints. All routes are prefixed with `/api/v1`.

---

## Authentication

### Admin Key (`X-Herald-Key` header)

Required for agent management, policy updates, and telemetry queries. Set via `HERALD_API_KEY` environment variable. When unset, Herald runs in **dev mode** (no auth required).

### Sidecar Token (`Authorization: Bearer` header)

Required for event ingestion, telemetry reporting, and policy fetching. Tokens are issued during agent registration and start with `hld_sk_`.

---

## Agent Management

### Register Agent

```
POST /api/v1/agents
```

**Auth:** Admin key

**Body:**

```json
{
  "agent_id": "my-agent",
  "display_name": "My Agent",
  "tier": "L1",
  "allowed_actions": ["file_read"],
  "denied_actions": ["delete_records"],
  "channels": ["ops"]
}
```

**Response:**

```json
{
  "ok": true,
  "existing": false,
  "agent_id": "my-agent",
  "token": "hld_sk_...",
  "policy": { ... }
}
```

Re-registering an existing agent returns the same token (`"existing": true`).

### List Agents

```
GET /api/v1/agents
```

**Auth:** Admin key

### Get Agent

```
GET /api/v1/agents/{agent_id}
```

**Auth:** Admin key. Returns 404 for unknown agents.

### Deregister Agent

```
DELETE /api/v1/agents/{agent_id}
```

**Auth:** Admin key. Returns 404 for unknown agents.

---

## Policy

### Get Agent Policy (Sidecar)

```
GET /api/v1/agents/{agent_id}/policy
```

**Auth:** Sidecar bearer token. Returns 403 if token doesn't match agent.

### Update Policy

```
PUT /api/v1/agents/{agent_id}/policy
```

**Auth:** Admin key

**Body** (all fields optional):

```json
{
  "tier": "L2",
  "allowed_actions": ["file_read", "file_write"],
  "denied_actions": ["delete_records"],
  "integrity": {
    "max_network_rtt_ms": 120.0,
    "max_network_jitter_ms": 30.0,
    "expected_providers": ["anthropic"],
    "allow_remote_session": false
  }
}
```

Each update increments the policy version.

### List Policy Presets

```
GET /api/v1/policy/presets
```

**Auth:** None (public). Returns standard, strict, and relaxed presets with their integrity thresholds.

### Apply Preset to Agent

```
POST /api/v1/agents/{agent_id}/policy/preset
```

**Auth:** Admin key

**Body:**

```json
{
  "preset": "strict",
  "pin_observed_claims": true
}
```

When `pin_observed_claims` is true, the agent's currently observed provider/model/region become the expected values in policy.

### Apply Preset to Fleet

```
POST /api/v1/fleet/policy/preset
```

**Auth:** Admin key

**Body:**

```json
{
  "preset": "standard",
  "agent_ids": ["agent-1", "agent-2"],
  "pin_observed_claims": false
}
```

Empty `agent_ids` applies to all registered agents.

---

## Events

### Ingest Event (Sidecar)

```
POST /api/v1/events
```

**Auth:** Sidecar bearer token. Token must match the event's `agent_id`.

**Body:**

```json
{
  "agent_id": "my-agent",
  "action": "file_read",
  "target": "/data/report.csv",
  "result": "success",
  "detail": "Read 1024 bytes",
  "duration_ms": 12
}
```

Heartbeat events (`"action": "heartbeat"`) update the agent's last heartbeat timestamp without counting as a regular event.

### Query Events (Audit Log)

```
GET /api/v1/events?agent_id=...&action=...&since=...&limit=100
```

**Auth:** None (public). Returns events most-recent-first.

| Parameter | Type | Description |
|-----------|------|-------------|
| `agent_id` | string | Filter by agent |
| `action` | string | Filter by action type |
| `since` | ISO 8601 | Only events after this timestamp |
| `limit` | int (1-1000) | Max results (default: 100) |

---

## Telemetry

### Ingest Telemetry (Sidecar)

```
POST /api/v1/telemetry
```

**Auth:** Sidecar bearer token

**Body:**

```json
{
  "agent_id": "my-agent",
  "probe_source": "sidecar",
  "network_rtt_ms": 2.5,
  "network_jitter_ms": 0.8,
  "is_remote_session": false,
  "observed_provider": "anthropic",
  "observed_model": "claude-3",
  "observed_region": "us-east-1"
}
```

Ingesting telemetry triggers an integrity assessment. The response includes the updated score and status.

### Query Telemetry

```
GET /api/v1/telemetry?agent_id=...&since=...&limit=100
```

**Auth:** Admin key

---

## Fleet Status

### Fleet Status

```
GET /api/v1/fleet/status
```

**Auth:** None (public). Returns all agents with health, tier, integrity, and last activity.

### Fleet Health

```
GET /api/v1/fleet/health
```

**Auth:** None (public). Returns aggregate counts: active, inactive, degraded, and integrity status distribution.

### Fleet Telemetry

```
GET /api/v1/fleet/telemetry?agent_id=...&since=...&limit=200
```

**Auth:** None (public). Returns telemetry timeline with scorecards (min, max, p50, p95) for dashboard visualization.
