# The Sidecar Pattern

The sidecar is the bridge between your agent and Switchboard. It handles all protocol communication so your agent doesn't have to.

---

## What the Sidecar Does

```
┌──────────────────────────┐
│   Your Agent Container    │
│                          │
│  ┌──────┐  ┌──────────┐ │
│  │Agent │──│ Sidecar   │─┼──── Switchboard API
│  │(any) │  │ (Python)  │ │     (port 59237)
│  └──────┘  └──────────┘ │
│     ▲           │        │
│     │    policy.json     │
│     └───────────┘        │
└──────────────────────────┘
```

The sidecar:

1. **Pulls policy** from Switchboard and writes it as a local file your agent reads
2. **Forwards events** from your agent (localhost:9100) to Switchboard
3. **Sends heartbeats** every 30 seconds to prove the agent is alive
4. **Reports telemetry** (network RTT, jitter, runtime claims) for integrity scoring

## Running the Sidecar

```bash
SWITCHBOARD_URL=http://localhost:59237 \
AGENT_ID=my-agent \
SIDECAR_TOKEN=swb_sk_... \
python sidecar/switchboard-sidecar.py
```

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SWITCHBOARD_URL` | `http://localhost:59237` | Switchboard API endpoint |
| `AGENT_ID` | *(required)* | Agent identifier |
| `SIDECAR_TOKEN` | *(required)* | Bearer token from registration |
| `SWITCHBOARD_API_KEY` | | Admin key (for auto-registration) |
| `POLICY_FORMAT` | `json` | Policy file format: `json`, `yaml`, `env`, `toml` |
| `POLICY_PATH` | `/switchboard/policy.json` | Where to write the policy file |
| `EVENT_LISTEN_PORT` | `9100` | Port for agent event submissions |
| `HEARTBEAT_INTERVAL` | `30` | Seconds between heartbeats |
| `TELEMETRY_INTERVAL` | `30` | Seconds between telemetry reports |
| `TELEMETRY_MODE` | `sidecar_only` | `sidecar_only` or `sidecar_plus_sensor` |
| `OBSERVED_PROVIDER` | | Runtime claim: AI provider (e.g., `anthropic`) |
| `OBSERVED_MODEL` | | Runtime claim: model name |
| `OBSERVED_REGION` | | Runtime claim: deployment region |

## Policy Formats

The sidecar writes policy in whatever format your agent prefers:

=== "JSON"

    ```json
    {
      "agent_id": "my-agent",
      "tier": "L2",
      "allowed_actions": ["file_read", "api_call"],
      "denied_actions": ["delete_records"]
    }
    ```

=== "YAML"

    ```yaml
    agent_id: my-agent
    tier: L2
    allowed_actions:
      - file_read
      - api_call
    denied_actions:
      - delete_records
    ```

=== "Environment"

    ```bash
    SWITCHBOARD_AGENT_ID=my-agent
    HERALD_TIER=L2
    HERALD_ALLOWED_ACTIONS=file_read,api_call
    HERALD_DENIED_ACTIONS=delete_records
    ```

## Auto-Registration

If you provide `SWITCHBOARD_API_KEY` instead of `SIDECAR_TOKEN`, the sidecar will register the agent automatically and store the token:

```bash
SWITCHBOARD_URL=http://localhost:59237 \
AGENT_ID=new-agent \
SWITCHBOARD_API_KEY=your-admin-key \
AGENT_TIER=L1 \
python sidecar/switchboard-sidecar.py
```

## Zero Dependencies

The reference sidecar uses only Python 3.11+ standard library. No pip install needed. Copy it into any container that has Python.

## Writing Your Own Sidecar

The sidecar protocol is simple enough to reimplement in any language. It needs to:

1. `GET /api/v1/agents/{id}/policy` with Bearer token — pull policy
2. `POST /api/v1/events` with Bearer token — forward events
3. `POST /api/v1/telemetry` with Bearer token — report telemetry
4. Listen on a local port for agent event POSTs

See the [Protocol Specification](PROTOCOL.md) for the full API contract.
