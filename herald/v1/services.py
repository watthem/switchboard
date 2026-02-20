"""Service layer for Herald v1 governance protocol.

File-backed JSON storage for POC. Replace with a real database on DEV.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .models import (
    AgentEvent,
    AgentPolicy,
    AgentRecord,
    AgentRegistration,
    AgentStatus,
    AgentStore,
    AgentTelemetry,
    EventStore,
    IntegrityAssessment,
    IntegrityPolicy,
    IntegrityStatus,
    PolicyUpdate,
    TelemetryStore,
)

logger = logging.getLogger("herald.v1.services")

# --- Storage paths (POC: JSON files) ---

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "v1"
_AGENTS_FILE = _DATA_DIR / "agents.json"
_EVENTS_FILE = _DATA_DIR / "events.json"
_TELEMETRY_FILE = _DATA_DIR / "telemetry.json"

# Heartbeat timeout — agent is "inactive" if no heartbeat in this window
_HEARTBEAT_TIMEOUT = timedelta(seconds=90)

# Max events kept in the file store (POC guard against unbounded growth)
_MAX_EVENTS = 10_000
_MAX_TELEMETRY = 10_000

_PRESET_ORDER = ("standard", "strict", "relaxed")
_INTEGRITY_POLICY_PRESETS: dict[str, dict] = {
    "standard": {
        "label": "Standard",
        "description": (
            "Balanced baseline for day-to-day operations. "
            "Allows sidecar telemetry, blocks remote sessions, moderate RTT/jitter limits."
        ),
        "integrity": {
            "telemetry_mode": "sidecar_only",
            "max_network_rtt_ms": 120.0,
            "max_network_jitter_ms": 30.0,
            "allow_remote_session": False,
        },
    },
    "strict": {
        "label": "Strict",
        "description": (
            "Tighter latency and locality policy for sensitive workloads. "
            "Requires sidecar+sensor mode and aggressive RTT/jitter thresholds."
        ),
        "integrity": {
            "telemetry_mode": "sidecar_plus_sensor",
            "max_network_rtt_ms": 70.0,
            "max_network_jitter_ms": 18.0,
            "allow_remote_session": False,
        },
    },
    "relaxed": {
        "label": "Relaxed",
        "description": (
            "Loose thresholds for distributed or unstable networks. "
            "Accepts higher latency and permits remote sessions."
        ),
        "integrity": {
            "telemetry_mode": "sidecar_only",
            "max_network_rtt_ms": 240.0,
            "max_network_jitter_ms": 70.0,
            "allow_remote_session": True,
        },
    },
}


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


# --- Agent store ---


def _load_agents() -> AgentStore:
    if not _AGENTS_FILE.exists():
        return AgentStore()
    try:
        data = json.loads(_AGENTS_FILE.read_text(encoding="utf-8"))
        return AgentStore(**data)
    except Exception:
        logger.exception("Failed to read agents.json")
        return AgentStore()


def _save_agents(store: AgentStore) -> None:
    _ensure_data_dir()
    _AGENTS_FILE.write_text(
        store.model_dump_json(indent=2), encoding="utf-8"
    )


# --- Event store ---


def _load_events() -> EventStore:
    if not _EVENTS_FILE.exists():
        return EventStore()
    try:
        data = json.loads(_EVENTS_FILE.read_text(encoding="utf-8"))
        return EventStore(**data)
    except Exception:
        logger.exception("Failed to read events.json")
        return EventStore()


def _save_events(store: EventStore) -> None:
    _ensure_data_dir()
    # Trim to max
    if len(store.events) > _MAX_EVENTS:
        store.events = store.events[-_MAX_EVENTS:]
    _EVENTS_FILE.write_text(
        store.model_dump_json(indent=2), encoding="utf-8"
    )


# --- Telemetry store ---


def _load_telemetry() -> TelemetryStore:
    if not _TELEMETRY_FILE.exists():
        return TelemetryStore()
    try:
        data = json.loads(_TELEMETRY_FILE.read_text(encoding="utf-8"))
        return TelemetryStore(**data)
    except Exception:
        logger.exception("Failed to read telemetry.json")
        return TelemetryStore()


def _save_telemetry(store: TelemetryStore) -> None:
    _ensure_data_dir()
    if len(store.telemetry) > _MAX_TELEMETRY:
        store.telemetry = store.telemetry[-_MAX_TELEMETRY:]
    _TELEMETRY_FILE.write_text(
        store.model_dump_json(indent=2), encoding="utf-8"
    )


# --- Token generation ---


def _generate_token() -> str:
    """Generate a sidecar auth token."""
    return f"hld_sk_{secrets.token_urlsafe(32)}"


# --- Agent management ---


def register_agent(reg: AgentRegistration) -> dict:
    """Register a new agent. Returns agent record with sidecar token."""
    store = _load_agents()

    if reg.agent_id in store.agents:
        existing = store.agents[reg.agent_id]
        return {
            "ok": True,
            "existing": True,
            "agent_id": existing.agent_id,
            "token": existing.token,
            "policy": existing.policy.model_dump(),
        }

    token = _generate_token()
    policy = AgentPolicy(
        agent_id=reg.agent_id,
        tier=reg.tier,
        allowed_actions=reg.allowed_actions,
        denied_actions=reg.denied_actions,
        channels=reg.channels,
        rate_limits=reg.rate_limits,
    )
    record = AgentRecord(
        agent_id=reg.agent_id,
        display_name=reg.display_name or reg.agent_id,
        policy=policy,
        token=token,
    )
    store.agents[reg.agent_id] = record
    _save_agents(store)

    return {
        "ok": True,
        "existing": False,
        "agent_id": reg.agent_id,
        "token": token,
        "policy": policy.model_dump(),
    }


def _serialize_agent_summary(record: AgentRecord) -> dict:
    return {
        "agent_id": record.agent_id,
        "display_name": record.display_name,
        "status": record.status.value,
        "tier": record.policy.tier.value,
        "last_heartbeat": record.last_heartbeat,
        "last_event": record.last_event,
        "last_telemetry": record.last_telemetry,
        "integrity_status": record.integrity.status.value,
        "integrity_score": record.integrity.score,
        "integrity_reasons": record.integrity.reasons,
        "observed_provider": record.observed_provider,
        "observed_model": record.observed_model,
        "observed_region": record.observed_region,
        "last_probe_source": (
            record.last_probe_source.value if record.last_probe_source else None
        ),
        "last_telemetry_mode": (
            record.last_telemetry_mode.value if record.last_telemetry_mode else None
        ),
        "last_network_rtt_ms": record.last_network_rtt_ms,
        "last_network_jitter_ms": record.last_network_jitter_ms,
        "last_sensor_hid_rtt_ms": record.last_sensor_hid_rtt_ms,
        "last_sensor_dwell_ms": record.last_sensor_dwell_ms,
        "last_sensor_os_jitter_ms": record.last_sensor_os_jitter_ms,
        "registered_at": record.registered_at,
    }


def list_agents() -> dict:
    """List all registered agents."""
    store = _load_agents()
    _refresh_statuses(store)

    agents = [_serialize_agent_summary(record) for record in store.agents.values()]
    return {"ok": True, "agents": agents}


def get_agent(agent_id: str) -> dict:
    """Get a single agent's full record."""
    store = _load_agents()
    record = store.agents.get(agent_id)
    if not record:
        return {"ok": False, "error": f"Agent '{agent_id}' not found"}

    _refresh_status(record)
    return {
        "ok": True,
        "agent_id": record.agent_id,
        "display_name": record.display_name,
        "status": record.status.value,
        "policy": record.policy.model_dump(),
        "registered_at": record.registered_at,
        "last_heartbeat": record.last_heartbeat,
        "last_event": record.last_event,
        "last_telemetry": record.last_telemetry,
        "integrity": record.integrity.model_dump(),
        "observed_provider": record.observed_provider,
        "observed_model": record.observed_model,
        "observed_region": record.observed_region,
        "last_probe_source": (
            record.last_probe_source.value if record.last_probe_source else None
        ),
        "last_telemetry_mode": (
            record.last_telemetry_mode.value if record.last_telemetry_mode else None
        ),
        "last_network_rtt_ms": record.last_network_rtt_ms,
        "last_network_jitter_ms": record.last_network_jitter_ms,
        "last_sensor_hid_rtt_ms": record.last_sensor_hid_rtt_ms,
        "last_sensor_dwell_ms": record.last_sensor_dwell_ms,
        "last_sensor_os_jitter_ms": record.last_sensor_os_jitter_ms,
    }


def update_policy(agent_id: str, update: PolicyUpdate) -> dict:
    """Update an agent's policy. Increments policy version."""
    store = _load_agents()
    record = store.agents.get(agent_id)
    if not record:
        return {"ok": False, "error": f"Agent '{agent_id}' not found"}

    policy = record.policy
    if update.tier is not None:
        policy.tier = update.tier
    if update.allowed_actions is not None:
        policy.allowed_actions = update.allowed_actions
    if update.denied_actions is not None:
        policy.denied_actions = update.denied_actions
    if update.channels is not None:
        policy.channels = update.channels
    if update.rate_limits is not None:
        policy.rate_limits = update.rate_limits
    if update.integrity is not None:
        policy.integrity = update.integrity
    policy.version += 1

    _save_agents(store)

    return {
        "ok": True,
        "agent_id": agent_id,
        "policy": policy.model_dump(),
    }


def list_policy_presets() -> dict:
    """List built-in integrity-policy presets."""
    presets: list[dict] = []
    for name in _PRESET_ORDER:
        cfg = _INTEGRITY_POLICY_PRESETS[name]
        policy = IntegrityPolicy(**cfg["integrity"])
        presets.append(
            {
                "name": name,
                "label": cfg["label"],
                "description": cfg["description"],
                "recommended": name == "standard",
                "integrity": policy.model_dump(),
            }
        )

    return {"ok": True, "default_preset": "standard", "presets": presets}


def apply_policy_preset(
    agent_id: str, preset: str, pin_observed_claims: bool = False
) -> dict:
    """Apply one of the built-in integrity-policy presets to a single agent."""
    normalized = str(preset).strip().lower()
    store = _load_agents()
    record = store.agents.get(agent_id)
    if not record:
        return {"ok": False, "error": f"Agent '{agent_id}' not found"}

    applied = _apply_preset_to_record(record, normalized, pin_observed_claims)
    if not applied:
        return {"ok": False, "error": f"Unknown policy preset '{preset}'"}

    latest_by_agent = _latest_telemetry_by_agent()
    latest = latest_by_agent.get(agent_id)
    if latest:
        record.integrity = _assess_integrity(record.policy, latest)

    _refresh_status(record)
    _save_agents(store)

    return {
        "ok": True,
        "agent_id": agent_id,
        "preset": normalized,
        "pin_observed_claims": pin_observed_claims,
        "policy": record.policy.model_dump(),
        "integrity": record.integrity.model_dump(),
    }


def apply_policy_preset_fleet(
    preset: str,
    agent_ids: list[str] | None = None,
    pin_observed_claims: bool = False,
) -> dict:
    """Apply one preset to some or all agents in one request."""
    normalized = str(preset).strip().lower()
    if normalized not in _INTEGRITY_POLICY_PRESETS:
        return {"ok": False, "error": f"Unknown policy preset '{preset}'"}

    store = _load_agents()
    target_ids = agent_ids or list(store.agents.keys())
    if not target_ids:
        return {
            "ok": True,
            "preset": normalized,
            "pin_observed_claims": pin_observed_claims,
            "applied": 0,
            "missing": [],
            "agents": [],
        }

    latest_by_agent = _latest_telemetry_by_agent()
    missing: list[str] = []
    updated: list[dict] = []

    for agent_id in target_ids:
        record = store.agents.get(agent_id)
        if not record:
            missing.append(agent_id)
            continue

        _apply_preset_to_record(record, normalized, pin_observed_claims)
        latest = latest_by_agent.get(agent_id)
        if latest:
            record.integrity = _assess_integrity(record.policy, latest)
        _refresh_status(record)
        updated.append(
            {
                "agent_id": agent_id,
                "policy_version": record.policy.version,
            }
        )

    _save_agents(store)
    return {
        "ok": True,
        "preset": normalized,
        "pin_observed_claims": pin_observed_claims,
        "applied": len(updated),
        "missing": missing,
        "agents": updated,
    }


def deregister_agent(agent_id: str) -> dict:
    """Remove an agent from the registry."""
    store = _load_agents()
    if agent_id not in store.agents:
        return {"ok": False, "error": f"Agent '{agent_id}' not found"}

    del store.agents[agent_id]
    _save_agents(store)
    return {"ok": True, "agent_id": agent_id, "deregistered": True}


def get_agent_policy(agent_id: str) -> dict:
    """Get an agent's current policy (used by sidecar)."""
    store = _load_agents()
    record = store.agents.get(agent_id)
    if not record:
        return {"ok": False, "error": f"Agent '{agent_id}' not found"}

    return record.policy.model_dump()


def validate_token(agent_id: str, token: str) -> bool:
    """Check if a sidecar token is valid for the given agent."""
    store = _load_agents()
    record = store.agents.get(agent_id)
    if not record:
        return False
    return record.token == token


# --- Event ingestion ---


def ingest_event(event: AgentEvent) -> dict:
    """Record an event from an agent/sidecar."""
    # Update agent record
    store = _load_agents()
    record = store.agents.get(event.agent_id)
    if record:
        now = datetime.now(timezone.utc).isoformat()
        if event.action == "heartbeat":
            record.last_heartbeat = now
        else:
            record.last_event = now
            record.last_heartbeat = now  # any event counts as alive
        _refresh_status(record)
        _save_agents(store)

    # Append to event log
    event_store = _load_events()
    event_store.events.append(event)
    _save_events(event_store)

    return {"ok": True, "event_id": len(event_store.events) - 1}


def query_events(
    agent_id: str | None = None,
    action: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> dict:
    """Query the audit log with optional filters."""
    event_store = _load_events()
    events = event_store.events

    if agent_id:
        events = [e for e in events if e.agent_id == agent_id]
    if action:
        events = [e for e in events if e.action == action]
    if since:
        events = [e for e in events if e.timestamp >= since]

    # Most recent first, apply limit
    events = list(reversed(events))[:limit]

    return {
        "ok": True,
        "count": len(events),
        "events": [e.model_dump() for e in events],
    }


# --- Telemetry ingestion ---


def ingest_telemetry(telemetry: AgentTelemetry) -> dict:
    """Record telemetry signals and update integrity status."""
    store = _load_agents()
    record = store.agents.get(telemetry.agent_id)
    if not record:
        return {"ok": False, "error": f"Agent '{telemetry.agent_id}' not found"}

    record.last_telemetry = telemetry.timestamp
    record.last_probe_source = telemetry.probe_source
    record.last_telemetry_mode = telemetry.telemetry_mode
    record.last_network_rtt_ms = telemetry.network_rtt_ms
    record.last_network_jitter_ms = telemetry.network_jitter_ms
    record.last_sensor_hid_rtt_ms = telemetry.sensor_hid_rtt_ms
    record.last_sensor_dwell_ms = telemetry.sensor_dwell_ms
    record.last_sensor_os_jitter_ms = telemetry.sensor_os_jitter_ms
    if telemetry.observed_provider:
        record.observed_provider = telemetry.observed_provider
    if telemetry.observed_model:
        record.observed_model = telemetry.observed_model
    if telemetry.observed_region:
        record.observed_region = telemetry.observed_region

    record.integrity = _assess_integrity(record.policy, telemetry)
    _refresh_status(record)
    _save_agents(store)

    telemetry_store = _load_telemetry()
    telemetry_store.telemetry.append(telemetry)
    _save_telemetry(telemetry_store)

    return {
        "ok": True,
        "agent_id": telemetry.agent_id,
        "integrity_status": record.integrity.status.value,
        "integrity_score": record.integrity.score,
        "integrity_reasons": record.integrity.reasons,
    }


def query_telemetry(
    agent_id: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> dict:
    """Query telemetry history with optional filters."""
    store = _load_telemetry()
    entries = store.telemetry

    if agent_id:
        entries = [t for t in entries if t.agent_id == agent_id]
    if since:
        entries = [t for t in entries if t.timestamp >= since]

    entries = list(reversed(entries))[:limit]
    return {
        "ok": True,
        "count": len(entries),
        "telemetry": [t.model_dump() for t in entries],
    }


def fleet_telemetry(
    agent_id: str | None = None,
    since: str | None = None,
    limit: int = 200,
) -> dict:
    """Public, read-only telemetry timeline with scorecards for dashboard UX."""
    telemetry_store = _load_telemetry()
    agents_store = _load_agents()
    entries = telemetry_store.telemetry

    if agent_id:
        entries = [t for t in entries if t.agent_id == agent_id]
    if since:
        entries = [t for t in entries if t.timestamp >= since]

    if limit > 0:
        entries = entries[-limit:]

    rtt_values: list[float] = []
    jitter_values: list[float] = []
    hid_values: list[float] = []
    dwell_values: list[float] = []
    os_jitter_values: list[float] = []
    high_latency_measured = 0
    remote_session_samples = 0
    per_agent: dict[str, dict] = {}
    timeline: list[dict] = []

    for telemetry in entries:
        record = agents_store.agents.get(telemetry.agent_id)
        if record:
            assessment = _assess_integrity(record.policy, telemetry)
            display_name = record.display_name
        else:
            assessment = IntegrityAssessment(
                status=IntegrityStatus.unknown,
                score=50,
                reasons=["agent_not_registered"],
                last_evaluated=datetime.now(timezone.utc).isoformat(),
            )
            display_name = telemetry.agent_id

        if assessment.status in {IntegrityStatus.elevated, IntegrityStatus.degraded}:
            high_latency_measured += 1
        if telemetry.is_remote_session:
            remote_session_samples += 1

        bucket = per_agent.setdefault(
            telemetry.agent_id,
            {
                "agent_id": telemetry.agent_id,
                "display_name": display_name,
                "samples": 0,
                "high_latency_measured": 0,
            },
        )
        bucket["samples"] += 1
        if assessment.status in {IntegrityStatus.elevated, IntegrityStatus.degraded}:
            bucket["high_latency_measured"] += 1

        if telemetry.network_rtt_ms is not None:
            rtt_values.append(telemetry.network_rtt_ms)
        if telemetry.network_jitter_ms is not None:
            jitter_values.append(telemetry.network_jitter_ms)
        if telemetry.sensor_hid_rtt_ms is not None:
            hid_values.append(telemetry.sensor_hid_rtt_ms)
        if telemetry.sensor_dwell_ms is not None:
            dwell_values.append(telemetry.sensor_dwell_ms)
        if telemetry.sensor_os_jitter_ms is not None:
            os_jitter_values.append(telemetry.sensor_os_jitter_ms)

        timeline.append(_serialize_telemetry_entry(telemetry, assessment))

    timeline = list(reversed(timeline))
    agents = sorted(
        list(per_agent.values()), key=lambda row: row["samples"], reverse=True
    )

    return {
        "ok": True,
        "agent_id": agent_id,
        "count": len(timeline),
        "telemetry": timeline,
        "summary": {
            "window_start": entries[0].timestamp if entries else None,
            "window_end": entries[-1].timestamp if entries else None,
            "high_latency_measured": high_latency_measured,
            "remote_session_samples": remote_session_samples,
            "metrics": {
                "network_rtt_ms": _build_scorecard(rtt_values),
                "network_jitter_ms": _build_scorecard(jitter_values),
                "sensor_hid_rtt_ms": _build_scorecard(hid_values),
                "sensor_dwell_ms": _build_scorecard(dwell_values),
                "sensor_os_jitter_ms": _build_scorecard(os_jitter_values),
            },
            "agents": agents,
        },
    }


# --- Fleet status ---


def fleet_status() -> dict:
    """All agents with health, tier, last event."""
    store = _load_agents()
    _refresh_statuses(store)
    _save_agents(store)

    agents = [_serialize_agent_summary(record) for record in store.agents.values()]
    return {"ok": True, "agents": agents}


def fleet_health() -> dict:
    """Aggregate fleet health counts."""
    store = _load_agents()
    _refresh_statuses(store)

    counts = {"active": 0, "inactive": 0, "degraded": 0, "total": 0}
    integrity = {"normal": 0, "elevated": 0, "degraded": 0, "unknown": 0}
    for record in store.agents.values():
        counts["total"] += 1
        counts[record.status.value] += 1
        integrity[record.integrity.status.value] += 1

    return {
        "ok": True,
        **counts,
        "integrity_normal": integrity["normal"],
        "integrity_elevated": integrity["elevated"],
        "integrity_degraded": integrity["degraded"],
        "integrity_unknown": integrity["unknown"],
    }


# --- Internal helpers ---


def _apply_preset_to_record(
    record: AgentRecord, preset: str, pin_observed_claims: bool
) -> IntegrityPolicy | None:
    cfg = _INTEGRITY_POLICY_PRESETS.get(preset)
    if not cfg:
        return None

    previous = record.policy.integrity
    integrity = IntegrityPolicy(**cfg["integrity"])
    if pin_observed_claims:
        integrity.expected_providers = (
            [record.observed_provider]
            if record.observed_provider
            else list(previous.expected_providers)
        )
        integrity.expected_models = (
            [record.observed_model]
            if record.observed_model
            else list(previous.expected_models)
        )
        integrity.expected_regions = (
            [record.observed_region]
            if record.observed_region
            else list(previous.expected_regions)
        )
    else:
        integrity.expected_providers = list(previous.expected_providers)
        integrity.expected_models = list(previous.expected_models)
        integrity.expected_regions = list(previous.expected_regions)

    record.policy.integrity = integrity
    record.policy.version += 1
    return integrity


def _latest_telemetry_by_agent() -> dict[str, AgentTelemetry]:
    latest: dict[str, AgentTelemetry] = {}
    telemetry_store = _load_telemetry()
    for telemetry in reversed(telemetry_store.telemetry):
        if telemetry.agent_id not in latest:
            latest[telemetry.agent_id] = telemetry
    return latest


def _serialize_telemetry_entry(
    telemetry: AgentTelemetry, assessment: IntegrityAssessment
) -> dict:
    return {
        "agent_id": telemetry.agent_id,
        "timestamp": telemetry.timestamp,
        "probe_source": telemetry.probe_source.value,
        "telemetry_mode": telemetry.telemetry_mode.value,
        "network_rtt_ms": telemetry.network_rtt_ms,
        "network_jitter_ms": telemetry.network_jitter_ms,
        "is_remote_session": telemetry.is_remote_session,
        "observed_provider": telemetry.observed_provider,
        "observed_model": telemetry.observed_model,
        "observed_region": telemetry.observed_region,
        "sensor_hid_rtt_ms": telemetry.sensor_hid_rtt_ms,
        "sensor_dwell_ms": telemetry.sensor_dwell_ms,
        "sensor_os_jitter_ms": telemetry.sensor_os_jitter_ms,
        "integrity_status": assessment.status.value,
        "integrity_score": assessment.score,
        "integrity_reasons": assessment.reasons,
    }


def _build_scorecard(values: list[float]) -> dict | None:
    if not values:
        return None

    sorted_values = sorted(values)
    return {
        "latest": round(values[-1], 2),
        "mean": round(sum(values) / len(values), 2),
        "min": round(sorted_values[0], 2),
        "max": round(sorted_values[-1], 2),
        "p50": round(_percentile(sorted_values, 0.5), 2),
        "p95": round(_percentile(sorted_values, 0.95), 2),
    }


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * percentile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    weight = position - lower_index
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + (upper - lower) * weight


def _refresh_statuses(store: AgentStore) -> None:
    """Update status for all agents based on heartbeat freshness."""
    for record in store.agents.values():
        _refresh_status(record)


def _refresh_status(record: AgentRecord) -> None:
    """Update a single agent's status based on heartbeat."""
    if not record.last_heartbeat:
        record.status = AgentStatus.inactive
        return

    try:
        last = datetime.fromisoformat(record.last_heartbeat)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now - last > _HEARTBEAT_TIMEOUT:
            record.status = AgentStatus.inactive
        else:
            if record.integrity.status in {
                IntegrityStatus.elevated,
                IntegrityStatus.degraded,
            }:
                record.status = AgentStatus.degraded
            else:
                record.status = AgentStatus.active
    except (ValueError, TypeError):
        record.status = AgentStatus.inactive


def _assess_integrity(
    policy: AgentPolicy, telemetry: AgentTelemetry
) -> IntegrityAssessment:
    """Apply policy-aware checks to telemetry and return an integrity assessment."""
    reasons: list[str] = []
    score = 100
    cfg = policy.integrity

    if telemetry.is_remote_session and not cfg.allow_remote_session:
        reasons.append("remote_session_detected")
        score -= 45

    if cfg.expected_providers:
        observed_provider = (telemetry.observed_provider or "").strip()
        if observed_provider:
            if observed_provider not in cfg.expected_providers:
                reasons.append(
                    f"provider_mismatch:{observed_provider} not in {cfg.expected_providers}"
                )
                score -= 35
        else:
            reasons.append("provider_missing")
            score -= 10

    if cfg.expected_models:
        observed_model = (telemetry.observed_model or "").strip()
        if observed_model:
            if observed_model not in cfg.expected_models:
                reasons.append(
                    f"model_mismatch:{observed_model} not in {cfg.expected_models}"
                )
                score -= 35
        else:
            reasons.append("model_missing")
            score -= 10

    if cfg.expected_regions:
        observed_region = (telemetry.observed_region or "").strip()
        if observed_region:
            if observed_region not in cfg.expected_regions:
                reasons.append(
                    f"region_mismatch:{observed_region} not in {cfg.expected_regions}"
                )
                score -= 20
        else:
            reasons.append("region_missing")
            score -= 5

    if (
        cfg.max_network_rtt_ms is not None
        and telemetry.network_rtt_ms is not None
        and telemetry.network_rtt_ms > cfg.max_network_rtt_ms
    ):
        multiple = telemetry.network_rtt_ms / cfg.max_network_rtt_ms
        if multiple >= 2.0:
            reasons.append(
                f"network_rtt_far_above_baseline:{telemetry.network_rtt_ms:.1f}ms>{cfg.max_network_rtt_ms:.1f}ms"
            )
            score -= 35
        else:
            reasons.append(
                f"network_rtt_above_baseline:{telemetry.network_rtt_ms:.1f}ms>{cfg.max_network_rtt_ms:.1f}ms"
            )
            score -= 20

    if (
        cfg.max_network_jitter_ms is not None
        and telemetry.network_jitter_ms is not None
        and telemetry.network_jitter_ms > cfg.max_network_jitter_ms
    ):
        multiple = telemetry.network_jitter_ms / cfg.max_network_jitter_ms
        if multiple >= 2.0:
            reasons.append(
                f"network_jitter_far_above_baseline:{telemetry.network_jitter_ms:.1f}ms>{cfg.max_network_jitter_ms:.1f}ms"
            )
            score -= 25
        else:
            reasons.append(
                f"network_jitter_above_baseline:{telemetry.network_jitter_ms:.1f}ms>{cfg.max_network_jitter_ms:.1f}ms"
            )
            score -= 15

    has_any_signal = any(
        [
            telemetry.network_rtt_ms is not None,
            telemetry.network_jitter_ms is not None,
            telemetry.observed_provider,
            telemetry.observed_model,
            telemetry.observed_region,
            telemetry.sensor_hid_rtt_ms is not None,
            telemetry.sensor_dwell_ms is not None,
            telemetry.sensor_os_jitter_ms is not None,
        ]
    )

    score = max(0, min(100, score))

    if not has_any_signal:
        status = IntegrityStatus.unknown
    elif score >= 80:
        status = IntegrityStatus.normal
    elif score >= 55:
        status = IntegrityStatus.elevated
    else:
        status = IntegrityStatus.degraded

    return IntegrityAssessment(
        status=status,
        score=score,
        reasons=reasons[:6],
        last_evaluated=datetime.now(timezone.utc).isoformat(),
    )
