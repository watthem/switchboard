# Security & Air-Gapping

Switchboard's security model relies on infrastructure-level enforcement, not agent cooperation.

---

## Threat Model

| Vector | Containment |
|--------|-------------|
| **Prompt injection** | Compromised model is trapped in its container. An L0 agent that gets injected still has no write mounts and no network. Damage ceiling is zero. |
| **Credential exfiltration** | Secrets live in Switchboard, not in agent containers. Agents receive processed data only. No agent can read another agent's environment. |
| **Lateral movement** | No direct agent-to-agent communication. All messages route through Switchboard. A compromised agent cannot discover or reach other agents. |
| **Rogue sidecar** | The sidecar runs as a separate process with its own auth token. Even if an agent compromises its sidecar, container-level enforcement (mounts, network) still holds. |

## Authentication

### Admin Key

All agent management operations require an `X-Switchboard-Key` header matching the `SWITCHBOARD_API_KEY` environment variable. When unset, Switchboard runs in **dev mode** with no auth — intended only for local development.

### Sidecar Tokens

Each agent receives a unique bearer token (`swb_sk_...`) at registration. Sidecar tokens:

- Are validated on every event, telemetry, and policy request
- Are scoped to a single agent (a token for agent A cannot submit events for agent B)
- Are generated with `secrets.token_urlsafe(32)` — 256 bits of entropy

## Integrity Scoring

Switchboard uses physics-based attestation to detect runtime anomalies:

- **Network RTT** — proves the agent runs on the expected network (localhost RTT ~1-3ms rules out remote proxying)
- **Network jitter** — high jitter suggests unstable or proxied connections
- **Runtime claims** — observed provider/model/region compared against policy expectations
- **Remote session detection** — flags when an agent appears to be running via a remote session

Integrity scores use a 100-point system with penalties for violations. See [Sensor Integration](sensor-integration.md) for adding hardware-level signals.

## Air-Gap Deployment

!!! note "Placeholder"
    Full air-gap documentation is under development.

Switchboard is designed to run on a local network with no internet dependency:

- The Switchboard API, sidecar, and dashboard have zero external network calls
- All Python dependencies can be pre-installed from a vendored wheel cache
- The dashboard is a single HTML file with no CDN imports
- Event and telemetry storage is local file-backed JSON

For fully air-gapped environments, pre-build the Python package and transfer via secure media.
