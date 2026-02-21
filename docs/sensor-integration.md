# Sensor Integration Guide

**Type:** How-To Guide
**Audience:** Engineers adding hardware-level integrity signals to a Switchboard-managed fleet
**Prerequisites:** Switchboard running, sidecar deployed alongside agent

---

## Overview

The Switchboard sidecar collects two kinds of telemetry out of the box:

1. **Network signals** — RTT and jitter measured by pinging Switchboard's `/health` endpoint
2. **Runtime claims** — provider, model, and region declared via environment variables

These are sufficient for most deployments. But for higher-assurance scenarios (strict integrity preset, compliance environments, trading floors), you can add a **local sensor agent** that measures hardware-level timing signals the sidecar can't reach on its own:

| Signal | What It Measures | Why It Matters |
|--------|-----------------|----------------|
| **HID RTT** | Keyboard input → kernel → application round-trip | Remote desktop adds 5-50ms+ that local input doesn't |
| **Key dwell** | Duration of key press/release cycle | RDP/VNC buffers create uniform dwell patterns distinct from human typing |
| **OS jitter** | Scheduler latency (sleep accuracy) | VMs and containers under load show 20-50ms variance vs ~5ms local |

These signals are physics-based: the speed of light through fiber adds ~5 microseconds per kilometer. A trans-Pacific proxy chain introduces minimum 75ms of latency before protocol overhead. No software can fake lower latency than physics allows.

## Architecture

```
┌──────────────┐     localhost:7878/ws     ┌──────────────┐
│ Sensor Agent │ ◄──────────────────────── │   Sidecar    │
│ (Rust/native)│   heartbeat with signals  │  (Python)    │
│              │                           │              │
│ Measures:    │                           │ Reads sensor │
│ - HID RTT   │                           │ values from  │
│ - Dwell      │     env vars or HTTP      │ env/HTTP and │
│ - OS jitter  │ ──────────────────────►   │ includes in  │
│ - LED RTT    │                           │ telemetry    │
└──────────────┘                           └──────┬───────┘
                                                  │
                                          POST /api/v1/telemetry
                                                  │
                                                  ▼
                                           ┌──────────────┐
                                           │   Switchboard     │
                                           │  (FastAPI)   │
                                           └──────────────┘
```

The sensor agent runs on the same host as the sidecar. It measures timing signals and makes them available to the sidecar via one of two methods:

1. **Environment variables** (simplest) — set `SENSOR_HID_RTT_MS`, `SENSOR_DWELL_MS`, `SENSOR_OS_JITTER_MS` on the sidecar process
2. **HTTP/WebSocket** (dynamic) — sensor agent exposes readings; a wrapper script polls and updates sidecar env

## Method 1: Static Environment Variables

If your sensor agent writes readings to a shared file or you have baseline measurements, set the values directly on the sidecar:

```bash
SWITCHBOARD_URL=http://localhost:59237 \
AGENT_ID=warehouse-monitor \
TELEMETRY_MODE=sidecar_plus_sensor \
OBSERVED_PROVIDER=anthropic \
OBSERVED_MODEL=claude-sonnet-4-5 \
OBSERVED_REGION=us-west-2 \
SENSOR_HID_RTT_MS=12.4 \
SENSOR_DWELL_MS=85.2 \
SENSOR_OS_JITTER_MS=3.1 \
python switchboard-sidecar.py
```

The sidecar includes these values in every telemetry POST to Switchboard. Switchboard evaluates them against the agent's integrity policy.

**Docker Compose example:**

```yaml
services:
  my-agent:
    image: my-org/my-agent:latest
    volumes:
      - policy:/switchboard:ro

  sensor:
    image: switchboard/sensor-agent:latest
    # Writes readings to shared volume
    volumes:
      - sensor-data:/sensor

  sidecar:
    build: ../sidecar
    environment:
      SWITCHBOARD_URL: http://switchboard:59237
      AGENT_ID: my-agent
      AGENT_TIER: L2
      TELEMETRY_MODE: sidecar_plus_sensor
      OBSERVED_PROVIDER: anthropic
      OBSERVED_MODEL: claude-sonnet-4-5
      OBSERVED_REGION: us-west-2
      SENSOR_HID_RTT_MS: "12.4"
      SENSOR_DWELL_MS: "85.2"
      SENSOR_OS_JITTER_MS: "3.1"
    volumes:
      - policy:/switchboard

volumes:
  policy:
  sensor-data:
```

## Method 2: Dynamic Sensor Polling

For live readings, run a wrapper that polls the sensor agent and restarts/updates the sidecar with fresh values. This is the pattern used by the lag-heart native agent:

```bash
#!/bin/bash
# poll-sensor.sh — reads sensor, exports to sidecar env
SENSOR_URL="http://localhost:7878"

while true; do
  readings=$(curl -s "$SENSOR_URL/readings" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$readings" ]; then
    export SENSOR_HID_RTT_MS=$(echo "$readings" | python3 -c "import sys,json; print(json.load(sys.stdin).get('hid_rtt_ms',''))")
    export SENSOR_DWELL_MS=$(echo "$readings" | python3 -c "import sys,json; print(json.load(sys.stdin).get('avg_dwell_ms',''))")
    export SENSOR_OS_JITTER_MS=$(echo "$readings" | python3 -c "import sys,json; print(json.load(sys.stdin).get('os_jitter_ms',''))")
  fi
  sleep 10
done
```

The sidecar reads `SENSOR_*` env vars on each telemetry cycle, so updating them in the process environment takes effect at the next interval.

## Sensor Signal Formats

All sensor values are floating-point milliseconds:

| Env Var | Type | Valid Range | Example |
|---------|------|-------------|---------|
| `SENSOR_HID_RTT_MS` | float | 0.1 - 500.0 | `12.4` |
| `SENSOR_DWELL_MS` | float | 5.0 - 500.0 | `85.2` |
| `SENSOR_OS_JITTER_MS` | float | 0.1 - 100.0 | `3.1` |

Values outside valid ranges are included but may trigger integrity warnings.

## Telemetry Mode

Set `TELEMETRY_MODE` to tell Switchboard what kind of signals to expect:

| Mode | Description | When to Use |
|------|-------------|-------------|
| `sidecar_only` | Network RTT/jitter + runtime claims only | Default. No sensor agent deployed. |
| `sidecar_plus_sensor` | All sidecar signals plus HID/dwell/OS jitter | Sensor agent is running alongside sidecar. |

Switchboard uses this to set appropriate baselines. A `sidecar_plus_sensor` agent with missing sensor signals will show as `elevated` rather than `unknown`.

## Integrity Policy Presets

Presets define thresholds for telemetry signals:

| Preset | RTT Limit | Jitter Limit | Remote Allowed | Sensor Required |
|--------|-----------|-------------|----------------|-----------------|
| **Relaxed** | 240 ms | 70 ms | Yes | No |
| **Standard** | 120 ms | 30 ms | No | No |
| **Strict** | 70 ms | 18 ms | No | Yes (`sidecar_plus_sensor`) |

Apply presets via the dashboard or API:

```bash
# Apply strict preset to one agent
curl -X POST http://localhost:59237/api/v1/agents/warehouse-monitor/policy/preset \
  -H "Content-Type: application/json" \
  -H "X-Switchboard-Key: $SWITCHBOARD_API_KEY" \
  -d '{"preset": "strict", "pin_observed_claims": true}'

# Apply standard preset to all agents
curl -X POST http://localhost:59237/api/v1/fleet/policy/preset \
  -H "Content-Type: application/json" \
  -H "X-Switchboard-Key: $SWITCHBOARD_API_KEY" \
  -d '{"preset": "standard", "pin_observed_claims": false}'
```

The `pin_observed_claims` flag locks the agent's currently observed provider, model, and region into its integrity policy. Any drift from those values triggers an integrity score penalty.

## Building a Sensor Agent

If you're building your own sensor agent (rather than using the reference implementation), expose these signals:

**Minimum viable sensor** — just HID timing:

```python
# Example: Python sensor that measures keyboard dwell
import time
from pynput import keyboard

dwell_samples = []
press_times = {}

def on_press(key):
    press_times[key] = time.perf_counter()

def on_release(key):
    if key in press_times:
        dwell = (time.perf_counter() - press_times.pop(key)) * 1000
        dwell_samples.append(dwell)
        if len(dwell_samples) > 100:
            dwell_samples.pop(0)

# Expose via HTTP for sidecar polling
# GET /readings → {"avg_dwell_ms": 82.5, "sample_count": 47}
```

**Full sensor** — see the Rust reference agent at `~/git/lag-heart/agent/` for HID, OS jitter, LED loopback, and remote-session detection.

## Verifying Integration

Once the sidecar is running with sensor signals:

1. Check the dashboard at `http://localhost:59237/dashboard`
2. Select your agent card — the metric grid should show HID RTT, Dwell, and OS Jitter values
3. The scorecard table shows rolling statistics (latest, mean, p50, p95, min, max)
4. The integrity badge should reflect the agent's score against its policy

**API check:**

```bash
# Query telemetry for a specific agent
curl "http://localhost:59237/api/v1/fleet/telemetry?agent_id=warehouse-monitor&limit=5"
```

The response includes per-sample integrity evaluations with `integrity_status`, `integrity_score`, and `integrity_reasons`.
