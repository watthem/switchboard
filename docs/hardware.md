# Hardware Recommendations

Switchboard is designed to run on modest local hardware. This page covers resource requirements and deployment considerations.

---

!!! note "Placeholder"
    This page is under development. The content below reflects the POC deployment profile.

## Minimum Requirements

Switchboard and its fleet of sidecars run comfortably on:

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 1 core | 2 cores |
| RAM | 512 MB | 1 GB |
| Disk | 100 MB | 1 GB (for event/telemetry logs) |
| Python | 3.11+ | 3.12 |
| Network | Localhost only (POC) | LAN for multi-host fleets |

## Storage Sizing

POC storage uses file-backed JSON with automatic trimming:

- **Events:** Capped at 10,000 entries (~5-10 MB)
- **Telemetry:** Capped at 10,000 entries (~5-10 MB)
- **Agent registry:** Unbounded (typically < 1 MB for < 100 agents)

## Sidecar Overhead

Each sidecar is a single Python process using only the standard library:

- **Memory:** ~15-30 MB per sidecar
- **CPU:** Negligible (HTTP calls every 30 seconds)
- **Network:** ~1 KB/minute per agent (heartbeats + telemetry)

## Integrity Signal Quality

For meaningful RTT-based integrity scoring, Switchboard should run on the same physical host as the agents. Network latency between Switchboard and sidecars is the primary integrity signal — running Switchboard on a remote server defeats this measurement.
