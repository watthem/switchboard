# Switchboard Onboarding: Ruby Agent

Get fleet visibility and audit trails for your Ruby agent in 5 minutes. No SDK, no framework, no rewrite.

## Prerequisites

- Docker and Docker Compose
- That's it.

## Quick Start

```bash
# Clone and navigate
git clone <switchboard-repo-url>
cd switchboard/examples/ruby-agent

# Start everything
docker compose up --build
```

You'll see three services start:

1. **Switchboard** — the governance protocol endpoint (port 59237)
2. **Sidecar** — registers your agent, syncs policy, forwards events
3. **Ruby agent** — the example agent (replace with yours)

Within seconds:

```
sidecar   | 12:00:01 [sidecar] Registered agent 'ruby-demo-agent' — token: swb_sk_...
sidecar   | 12:00:01 [sidecar] Policy written to /switchboard/policy.json (json)
sidecar   | 12:00:01 [sidecar] Sidecar ready for agent 'ruby-demo-agent'
ruby-agent| [agent] Policy loaded: tier=L1, actions=read_data, query_api, send_notification
ruby-agent| [agent] Event reported: read_data → inventory.products (200)
```

## Check Fleet Status

```bash
# Fleet overview
curl http://localhost:59237/api/v1/fleet/status | jq

# Audit log
curl http://localhost:59237/api/v1/events | jq

# Agent policy
curl http://localhost:59237/api/v1/agents/ruby-demo-agent | jq
```

## Change Policy Live

Update the agent's tier while it's running:

```bash
# Promote to L2 (gets send_notification access)
curl -X PUT http://localhost:59237/api/v1/agents/ruby-demo-agent/policy \
  -H "Content-Type: application/json" \
  -d '{"tier": "L2"}'
```

The sidecar picks up the change and rewrites the policy file. The agent reads the new policy on its next cycle — no restart needed.

## Use With YOUR Agent

Replace the example Ruby agent with your own. Your agent only needs to do two things:

### 1. Read policy

The sidecar writes a policy file to `/switchboard/policy.json` (mounted read-only into your container). Read it however you want:

```ruby
policy = JSON.parse(File.read('/switchboard/policy.json'))
tier = policy['tier']              # "L0", "L1", "L2", "L3"
allowed = policy['allowed_actions'] # ["read_data", "query_api", ...]
```

### 2. Report events

POST to the sidecar at `http://sidecar:9100/events`:

```ruby
require 'net/http'
require 'json'

def report(action, target, result = 'success')
  uri = URI('http://sidecar:9100/events')
  Net::HTTP.post(uri, {
    action: action,
    target: target,
    result: result
  }.to_json, 'Content-Type' => 'application/json')
end

# Use it
report('read_data', 'users.csv')
report('query_api', 'api.stripe.com/charges', 'success')
report('send_email', 'team@company.com', 'denied')  # Policy blocked this
```

### 3. Update docker-compose.yaml

Replace the `ruby-agent` service with your image:

```yaml
services:
  # Keep switchboard and sidecar as-is, just change this:
  my-agent:
    image: my-org/my-agent:latest
    volumes:
      - policy:/switchboard:ro
    depends_on:
      - sidecar
    environment:
      SIDECAR_URL: http://sidecar:9100
```

## What You Get

Without changing a line of your agent's existing code (beyond adding the 3-line report function):

- **Fleet dashboard data** — `GET /api/v1/fleet/status` shows all agents, health, tier
- **Audit trail** — `GET /api/v1/events` shows every action with timestamp and attribution
- **Policy enforcement** — change tier from the API, agent reads updated policy
- **Health monitoring** — sidecar heartbeats every 30s, inactive agents flagged

## Architecture

```
┌──────────────────────────────────────┐
│         docker compose               │
│                                      │
│  ┌─────────┐   ┌─────────────────┐  │
│  │  Switchboard  │◄──│    Sidecar      │  │
│  │  :59237   │   │  (registers,    │  │
│  │          │   │   heartbeats,   │  │
│  │  Policy  │──►│   policy sync)  │  │
│  │  Events  │   └────────▲────────┘  │
│  │  Fleet   │            │ localhost  │
│  └─────────┘   ┌────────┴────────┐  │
│                │   Your Agent     │  │
│                │   (Ruby, Go,     │  │
│                │    Python, any)  │  │
│                │                  │  │
│                │ Reads: policy.json│  │
│                │ Posts: /events    │  │
│                └──────────────────┘  │
└──────────────────────────────────────┘
```

## Cleanup

```bash
docker compose down -v
```
