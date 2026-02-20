# Herald Protocol Specification

**Version:** 0.1.0
**Status:** Draft
**Last updated:** 2026-02-19
**Type:** Reference

---

Herald is the governance protocol that connects any AI agent to the Herald control plane. It defines a minimal contract: policy in, events out. Any agent in any language can integrate by implementing this contract.

## Overview

The Herald protocol has three directions and one enforcement layer:

| Direction | What | Transport | Who Implements |
|-----------|------|-----------|----------------|
| **Policy In** | Herald tells the agent what it's allowed to do | Local file or env vars | Sidecar (provided) |
| **Events Out** | Agent tells Herald what it did | HTTP POST to local sidecar | Agent developer (~3 lines) |
| **Telemetry Out** | Sidecar/sensor emits integrity signals and claims | HTTP POST to Herald | Sidecar (built-in) |
| **Enforcement** | Infrastructure limits that don't require agent cooperation | Container config | Herald (automatic) |

The sidecar handles all Herald communication. The agent only needs to: (1) read a local policy file, and (2) POST events to `localhost`.

## Events (Agent → Herald)

### Event Schema

Every event is a JSON object with five required fields:

```json
{
  "agent_id": "string",
  "timestamp": "ISO 8601",
  "action": "string",
  "target": "string",
  "result": "success | failure | pending | denied"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Unique identifier for this agent instance |
| `timestamp` | string | ISO 8601 timestamp of when the action occurred |
| `action` | string | What the agent did (e.g., `read_file`, `api_call`, `send_message`) |
| `target` | string | What the action operated on (e.g., `inventory.csv`, `slack.#general`) |
| `result` | enum | Outcome: `success`, `failure`, `pending` (awaiting HITL), `denied` (policy blocked) |

Optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `detail` | string | Human-readable description of what happened |
| `duration_ms` | integer | How long the action took |
| `tier` | string | Agent's tier at time of action (L0–L3) |
| `request_id` | string | Correlation ID for multi-step operations |

### Event Types

Agents emit events by POSTing to the sidecar at `http://localhost:9100/events`.

**Action taken** — the primary event. Emitted after every meaningful action:

```json
{
  "agent_id": "warehouse-monitor",
  "timestamp": "2026-02-18T14:32:01Z",
  "action": "update_stock_level",
  "target": "inventory.sku.A1234",
  "result": "success"
}
```

**Permission request** — when an L2 agent needs HITL approval:

```json
{
  "agent_id": "warehouse-monitor",
  "timestamp": "2026-02-18T14:32:05Z",
  "action": "request_permission",
  "target": "delete_expired_records",
  "result": "pending",
  "detail": "47 records older than 90 days"
}
```

**Error** — when something goes wrong:

```json
{
  "agent_id": "warehouse-monitor",
  "timestamp": "2026-02-18T14:32:10Z",
  "action": "api_call",
  "target": "https://supplier.example.com/api/reorder",
  "result": "failure",
  "detail": "Connection refused"
}
```

### Heartbeat

The sidecar handles heartbeats automatically. No agent implementation required. The sidecar POSTs to Herald every 30 seconds:

```json
{
  "agent_id": "warehouse-monitor",
  "timestamp": "2026-02-18T14:32:30Z",
  "action": "heartbeat",
  "target": "self",
  "result": "success"
}
```

### Telemetry Signals

**Why telemetry matters.** Agent governance without attestation is guesswork. A policy can declare that an agent runs Anthropic's Claude on `us-west-2`, but without measurement, that claim is unverifiable. Telemetry closes this gap by applying a physics-based principle: latency is unfakeable. A keystroke traveling from a local machine takes 20-50ms. The same keystroke routed through a trans-Pacific VPN or remote desktop takes 110ms+. Network RTT, jitter, and HID timing create a fingerprint that no proxy can hide because the speed of light through fiber adds ~5 microseconds per kilometer. Combined with runtime claims (provider, model, region) and remote-session detection, Herald can score the integrity of every agent in the fleet — not by trusting what agents say, but by measuring what the infrastructure reveals.

Sidecars may POST integrity telemetry directly to Herald. This is additive and runtime-agnostic.

```json
{
  "agent_id": "warehouse-monitor",
  "timestamp": "2026-02-18T14:33:00Z",
  "probe_source": "sidecar",
  "telemetry_mode": "sidecar_only",
  "network_rtt_ms": 12.4,
  "network_jitter_ms": 1.8,
  "is_remote_session": false,
  "observed_provider": "anthropic",
  "observed_model": "claude-sonnet-4-5",
  "observed_region": "us-west-2"
}
```

Optional sensor fields can be included when available:
- `sensor_hid_rtt_ms`
- `sensor_dwell_ms`
- `sensor_os_jitter_ms`

Herald evaluates telemetry against policy integrity constraints and exposes:
- `integrity_status` (`normal` | `elevated` | `degraded` | `unknown`)
- `integrity_score` (0–100)
- `integrity_reasons` (human-readable mismatch or threshold reasons)

For dashboard UX, Herald also exposes a public telemetry timeline endpoint with:
- recent per-sample integrity evaluations
- rolling scorecards (latest/mean/p50/p95/min/max)
- high-latency and remote-session sample counts

## Policy (Herald → Agent)

The sidecar pulls policy from Herald and writes it as a local file. The agent reads this file in whatever format its runtime prefers.

### Policy Schema

```yaml
agent_id: warehouse-monitor
tier: L2
version: 3                        # Increments on policy change

allowed_actions:
  - read_inventory
  - update_stock_level
  - send_alert

denied_actions:
  - delete_records
  - access_credentials
  - modify_network

rate_limits:
  events_per_minute: 60
  external_api_calls_per_minute: 10

channels:
  - inventory-alerts
  - warehouse-ops

credentials:                       # Injected by sidecar, not stored in agent container
  SUPPLIER_API_KEY: "injected-at-runtime"
```

### Policy Formats

The sidecar writes policy in the format configured for the agent:

| Format | File | Use Case |
|--------|------|----------|
| YAML | `/herald/policy.yaml` | Python, Ruby agents |
| JSON | `/herald/policy.json` | Node.js, Go agents |
| ENV | `/herald/.env` | Simple agents, shell scripts |
| TOML | `/herald/policy.toml` | Rust agents |

The sidecar watches for policy updates from Herald and rewrites the local file. Agents can either re-read on each action or watch the file for changes.

### Policy Delivery

The sidecar polls Herald for policy updates:

```
GET /api/v1/agents/{agent_id}/policy
Authorization: Bearer {sidecar_token}
```

Response:

```json
{
  "agent_id": "warehouse-monitor",
  "tier": "L2",
  "version": 3,
  "allowed_actions": ["read_inventory", "update_stock_level", "send_alert"],
  "denied_actions": ["delete_records", "access_credentials"],
  "rate_limits": {"events_per_minute": 60, "external_api_calls_per_minute": 10},
  "channels": ["inventory-alerts", "warehouse-ops"]
}
```

### Integrity Policy Presets

Herald ships built-in integrity presets to reduce manual policy edits:

- `standard` (recommended) - balanced thresholds for day-to-day operations
- `strict` - tighter latency thresholds for sensitive workloads
- `relaxed` - higher thresholds for unstable/distributed networks

Presets can be listed and applied via API, with optional claim pinning (use current observed provider/model/region as expected values).

## Sidecar

The sidecar is a lightweight process that runs alongside the agent container. It handles all Herald protocol communication so the agent doesn't have to.

### What the Sidecar Does

1. **Registers** the agent with Herald on startup
2. **Pulls policy** from Herald and writes it locally
3. **Accepts events** from the agent on `localhost:9100`
4. **Forwards events** to Herald with authentication
5. **Sends heartbeats** every 30 seconds
6. **Watches for policy changes** and updates the local file

### Sidecar Configuration

```yaml
# herald-sidecar.yaml
herald_url: https://herald.example.com
agent_id: warehouse-monitor
sidecar_token: hld_sk_...
policy_format: yaml              # yaml | json | env | toml
policy_path: /herald/policy.yaml
event_listen_port: 9100
heartbeat_interval_seconds: 30
```

### Deployment

The sidecar runs as a second container in the same pod (Kubernetes) or service (Docker Compose):

```yaml
# docker-compose.yaml
services:
  warehouse-monitor:
    image: my-org/warehouse-agent:latest
    volumes:
      - herald-policy:/herald:ro    # Read-only policy mount
    # No direct network access to Herald — goes through sidecar

  warehouse-monitor-sidecar:
    image: herald/sidecar:latest
    environment:
      HERALD_URL: https://herald.example.com
      AGENT_ID: warehouse-monitor
      SIDECAR_TOKEN: ${SIDECAR_TOKEN}
      POLICY_FORMAT: yaml
    volumes:
      - herald-policy:/herald       # Writes policy for agent to read
    ports:
      - "9100"                          # Internal only — agent posts events here

volumes:
  herald-policy:
```

## Integration Examples

### Python (3 lines)

```python
import httpx

def report(action: str, target: str, result: str = "success"):
    httpx.post("http://localhost:9100/events", json={
        "agent_id": AGENT_ID,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "target": target,
        "result": result,
    })
```

### Ruby (3 lines)

```ruby
require 'net/http'
require 'json'

def report(action, target, result = "success")
  uri = URI("http://localhost:9100/events")
  Net::HTTP.post(uri, {
    agent_id: AGENT_ID,
    timestamp: Time.now.utc.iso8601,
    action: action,
    target: target,
    result: result
  }.to_json, "Content-Type" => "application/json")
end
```

### Go (3 lines equivalent)

```go
func report(action, target, result string) error {
    event := map[string]string{
        "agent_id":  agentID,
        "timestamp": time.Now().UTC().Format(time.RFC3339),
        "action":    action,
        "target":    target,
        "result":    result,
    }
    body, _ := json.Marshal(event)
    _, err := http.Post("http://localhost:9100/events", "application/json", bytes.NewReader(body))
    return err
}
```

### curl (for testing)

```bash
curl -X POST http://localhost:9100/events \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "action": "test_action",
    "target": "test_target",
    "result": "success"
  }'
```

## Herald API (Control Plane ↔ Herald)

These endpoints are used by the control plane UI and admin tools, not by agents directly.

### Agent Management

```
POST   /api/v1/agents                    # Register new agent
GET    /api/v1/agents                    # List all agents
GET    /api/v1/agents/{agent_id}         # Get agent status
PUT    /api/v1/agents/{agent_id}/policy  # Update agent policy
GET    /api/v1/policy/presets            # List built-in integrity presets
POST   /api/v1/agents/{agent_id}/policy/preset  # Apply preset to one agent
POST   /api/v1/fleet/policy/preset       # Apply preset to some/all agents
DELETE /api/v1/agents/{agent_id}         # Deregister agent
```

### Event Ingestion

```
POST   /api/v1/events                    # Receive events (from sidecars)
POST   /api/v1/telemetry                 # Receive telemetry signals (from sidecars/sensors)
```

### Audit Log

```
GET    /api/v1/events                    # Query audit log
GET    /api/v1/events?agent_id=X         # Filter by agent
GET    /api/v1/events?action=Y           # Filter by action type
GET    /api/v1/events?since=ISO8601      # Filter by time
```

### Fleet Status

```
GET    /api/v1/fleet/status              # All agents with health, tier, last event
GET    /api/v1/fleet/health              # Aggregate health (up/down/degraded counts)
GET    /api/v1/fleet/telemetry           # Public telemetry timeline + scorecards
GET    /api/v1/telemetry                 # Query full telemetry history (admin)
```

## Security

### Authentication

- **Sidecar → Herald:** Bearer token (`hld_sk_...`) issued during agent registration
- **Control Plane → Herald:** API key with admin scope
- **Agent → Sidecar:** No auth required (localhost only, not exposed externally)

### Token Scopes

| Scope | Can Do |
|-------|--------|
| `agent:events` | Post events, read own policy |
| `agent:policy` | Read/write policy for assigned agents |
| `fleet:read` | Read fleet status, query audit log |
| `fleet:admin` | Register/deregister agents, modify any policy |

## Versioning

The Herald protocol uses semantic versioning. Breaking changes increment the major version and are announced with a deprecation period.

- Current: `v1` (draft)
- Endpoint prefix: `/api/v1/`
- Policy schema includes a `version` field for change detection
