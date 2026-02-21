# Quickstart

Get Switchboard running with example agents in under 60 seconds.

---

## Prerequisites

- Python 3.11+
- Git

## 1. Clone and Install

```bash
git clone https://github.com/watthem/switchboard.git
cd switchboard
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## 2. Start Switchboard

```bash
uvicorn switchboard.app:app --port 59237
```

Open [http://localhost:59237/dashboard](http://localhost:59237/dashboard) — you should see an empty fleet dashboard.

## 3. Register Example Agents

In a second terminal:

```bash
source .venv/bin/activate
python examples/register-fleet.py
```

Refresh the dashboard. You'll see registered agents with their tiers and integrity status.

## 4. Run a Sidecar

Start a sidecar for one of the registered agents:

```bash
SWITCHBOARD_URL=http://localhost:59237 \
AGENT_ID=my-agent \
SIDECAR_TOKEN=<token from registration> \
python sidecar/switchboard-sidecar.py
```

The sidecar will:

- Pull policy from Switchboard and write it locally
- Send heartbeats every 30 seconds
- Report telemetry (RTT, jitter) for integrity scoring
- Listen on `http://localhost:9100` for agent events

## 5. Send a Test Event

```bash
curl -X POST http://localhost:9100/events \
  -H "Content-Type: application/json" \
  -d '{"action":"file_read","target":"/etc/hostname","result":"success"}'
```

Check the dashboard — the agent's last event and heartbeat should update.

## Next Steps

- [Local Development](local-development.md) — run with `--reload`, run tests
- [Connecting Your First Agent](first-agent.md) — integrate a real agent
- [Autonomy Tiers](autonomy-tiers.md) — understand L0 through L3
