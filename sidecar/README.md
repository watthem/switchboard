# Switchboard Sidecar

Connects any agent to the Switchboard governance protocol. Zero external dependencies — runs on Python 3.11+ stdlib only.

## What it does

1. **Registers** your agent with Switchboard on startup
2. **Pulls policy** and writes it locally (JSON, YAML, TOML, or env vars)
3. **Listens** on `localhost:9100` for events from your agent
4. **Forwards** events to Switchboard with auth
5. **Heartbeats** every 30 seconds
6. **Telemetry signals** every 30 seconds (RTT/jitter + optional model/location claims)

## Quick start

```bash
# Start Switchboard first
cd ../switchboard && uvicorn switchboard.app:app --port 59237

# Run the sidecar
SWITCHBOARD_URL=http://localhost:59237 \
AGENT_ID=my-agent \
AGENT_TIER=L1 \
POLICY_PATH=./policy.json \
python switchboard-sidecar.py
```

The sidecar registers, pulls policy, and starts listening. Your agent posts events to `http://localhost:9100/events`.

## Docker Compose (with your agent)

```yaml
services:
  my-agent:
    image: my-org/my-agent:latest
    volumes:
      - policy:/switchboard:ro
    depends_on:
      - sidecar

  sidecar:
    build: .
    environment:
      SWITCHBOARD_URL: http://switchboard:59237
      AGENT_ID: my-agent
      AGENT_TIER: L1
      POLICY_FORMAT: json
      POLICY_PATH: /switchboard/policy.json
    volumes:
      - policy:/switchboard

volumes:
  policy:
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `SWITCHBOARD_URL` | `http://localhost:59237` | Switchboard endpoint |
| `AGENT_ID` | (required) | Unique agent identifier |
| `SIDECAR_TOKEN` | (auto-registered) | Bearer token for Switchboard auth |
| `SWITCHBOARD_API_KEY` | | Admin key for registration |
| `AGENT_TIER` | `L0` | Autonomy tier (L0-L3) |
| `AGENT_DISPLAY_NAME` | same as AGENT_ID | Human-readable name |
| `POLICY_FORMAT` | `json` | json, yaml, env, toml |
| `POLICY_PATH` | `/switchboard/policy.json` | Where to write policy |
| `EVENT_LISTEN_PORT` | `9100` | Port for agent event POSTs |
| `HEARTBEAT_INTERVAL` | `30` | Seconds between heartbeats |
| `TELEMETRY_INTERVAL` | `HEARTBEAT_INTERVAL` | Seconds between telemetry posts |
| `TELEMETRY_MODE` | `sidecar_only` | `sidecar_only` or `sidecar_plus_sensor` |
| `OBSERVED_PROVIDER` | | Runtime/provider claim (e.g. anthropic, openai) |
| `OBSERVED_MODEL` | | Runtime model claim (e.g. claude-sonnet-4-5) |
| `OBSERVED_REGION` | | Region/location claim (e.g. us-west-2) |
| `REMOTE_SESSION_HINT` | | Override remote-session signal (`true` / `false`) |
| `SENSOR_HID_RTT_MS` | | Optional local sensor signal (HID RTT ms) |
| `SENSOR_DWELL_MS` | | Optional local sensor signal (key dwell ms) |
| `SENSOR_OS_JITTER_MS` | | Optional local sensor signal (OS jitter ms) |
| `ALLOWED_ACTIONS` | | Comma-separated action list |
| `AGENT_CHANNELS` | | Comma-separated channel list |

## Agent integration

Your agent posts events to the sidecar at `http://localhost:9100/events`:

```json
{
  "action": "read_data",
  "target": "inventory.csv",
  "result": "success"
}
```

The `agent_id` and `timestamp` are set by the sidecar. The sidecar forwards to Switchboard with auth.

## Endpoints

| Path | Method | Description |
|------|--------|-------------|
| `/events` | POST | Accept event from agent, forward to Switchboard |
| `/health` | GET | Sidecar health check |
| `/policy` | GET | Current policy (for agents that prefer HTTP over file reads) |
