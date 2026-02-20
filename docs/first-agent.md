# Connecting Your First Agent

Integrate any agent with Herald in three steps: register, run the sidecar, emit events.

---

## Overview

Herald doesn't care what language your agent uses or how it's built. The integration contract is:

1. Your agent **reads a local policy file** (written by the sidecar)
2. Your agent **POSTs events to localhost:9100** (forwarded by the sidecar)

That's it. No SDK, no schema conformance, no framework adoption.

## Step 1: Register the Agent

```bash
curl -X POST http://localhost:59237/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "X-Herald-Key: $HERALD_API_KEY" \
  -d '{
    "agent_id": "my-agent",
    "display_name": "My First Agent",
    "tier": "L1",
    "allowed_actions": ["file_read", "api_call"],
    "channels": ["ops"]
  }'
```

Save the `token` from the response — the sidecar needs it.

## Step 2: Run the Sidecar

```bash
HERALD_URL=http://localhost:59237 \
AGENT_ID=my-agent \
SIDECAR_TOKEN=hld_sk_... \
python sidecar/herald-sidecar.py
```

The sidecar will:

- Pull policy from Herald and write `policy.json` locally
- Start heartbeat and telemetry loops
- Listen on `http://localhost:9100` for your agent's events

## Step 3: Emit Events from Your Agent

=== "Python"

    ```python
    import httpx

    def report(action: str, target: str, result: str = "success"):
        httpx.post("http://localhost:9100/events", json={
            "action": action,
            "target": target,
            "result": result,
        })

    # Usage
    report("file_read", "/data/inventory.csv")
    report("api_call", "https://api.example.com/status")
    ```

=== "Ruby"

    ```ruby
    require 'net/http'
    require 'json'

    def report(action, target, result = "success")
      uri = URI("http://localhost:9100/events")
      Net::HTTP.post(uri,
        { action: action, target: target, result: result }.to_json,
        "Content-Type" => "application/json")
    end

    # Usage
    report("file_read", "/data/inventory.csv")
    ```

=== "Go"

    ```go
    func report(action, target, result string) error {
        body, _ := json.Marshal(map[string]string{
            "action": action, "target": target, "result": result,
        })
        _, err := http.Post("http://localhost:9100/events",
            "application/json", bytes.NewReader(body))
        return err
    }
    ```

## Step 4: Read Policy (Optional)

The sidecar writes your agent's policy to a local file. Your agent can read it to make runtime decisions:

```python
import json
from pathlib import Path

policy = json.loads(Path("/herald/policy.json").read_text())
if "delete_records" in policy.get("denied_actions", []):
    raise PermissionError("Herald policy denies delete_records")
```

## Verify

Check the [dashboard](http://localhost:59237/dashboard) — your agent should appear with its tier, integrity score, and last event timestamp.

## Next Steps

- [Autonomy Tiers](autonomy-tiers.md) — choose the right tier for your agent
- [The Sidecar Pattern](sidecar.md) — configure heartbeat, telemetry, policy format
- [Protocol Specification](PROTOCOL.md) — full event schema and API reference
