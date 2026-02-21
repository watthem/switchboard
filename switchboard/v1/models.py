"""Pydantic models for Switchboard v1 governance protocol."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EventResult(str, Enum):
    success = "success"
    failure = "failure"
    pending = "pending"
    denied = "denied"


class AgentEvent(BaseModel):
    """An event emitted by an agent (or its sidecar)."""

    agent_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    action: str
    target: str
    result: EventResult = EventResult.success
    detail: str | None = None
    duration_ms: int | None = None
    tier: str | None = None
    request_id: str | None = None


class AgentTier(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class IntegrityStatus(str, Enum):
    normal = "normal"
    elevated = "elevated"
    degraded = "degraded"
    unknown = "unknown"


class TelemetryProbeSource(str, Enum):
    sidecar = "sidecar"
    sensor = "sensor"
    mixed = "mixed"
    manual = "manual"
    hook = "hook"


class TelemetryMode(str, Enum):
    sidecar_only = "sidecar_only"
    sidecar_plus_sensor = "sidecar_plus_sensor"


class IntegrityPreset(str, Enum):
    relaxed = "relaxed"
    standard = "standard"
    strict = "strict"


class RateLimits(BaseModel):
    events_per_minute: int = 60
    external_api_calls_per_minute: int = 10


class IntegrityPolicy(BaseModel):
    """Policy constraints used for integrity/attestation checks."""

    telemetry_mode: TelemetryMode = TelemetryMode.sidecar_only
    expected_providers: list[str] = Field(default_factory=list)
    expected_models: list[str] = Field(default_factory=list)
    expected_regions: list[str] = Field(default_factory=list)
    max_network_rtt_ms: float | None = None
    max_network_jitter_ms: float | None = None
    allow_remote_session: bool = False


class AgentPolicy(BaseModel):
    """Policy pushed to an agent via its sidecar."""

    agent_id: str
    tier: AgentTier = AgentTier.L0
    version: int = 1
    allowed_actions: list[str] = Field(default_factory=list)
    denied_actions: list[str] = Field(default_factory=list)
    rate_limits: RateLimits = Field(default_factory=RateLimits)
    channels: list[str] = Field(default_factory=list)
    integrity: IntegrityPolicy = Field(default_factory=IntegrityPolicy)


class AgentRegistration(BaseModel):
    """Request to register a new agent with Switchboard."""

    agent_id: str
    display_name: str | None = None
    tier: AgentTier = AgentTier.L0
    allowed_actions: list[str] = Field(default_factory=list)
    denied_actions: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    rate_limits: RateLimits = Field(default_factory=RateLimits)


class PolicyUpdate(BaseModel):
    """Request to update an agent's policy."""

    tier: AgentTier | None = None
    allowed_actions: list[str] | None = None
    denied_actions: list[str] | None = None
    channels: list[str] | None = None
    rate_limits: RateLimits | None = None
    integrity: IntegrityPolicy | None = None


class PolicyPresetApply(BaseModel):
    """Apply an integrity-policy preset to a single agent."""

    preset: IntegrityPreset = IntegrityPreset.standard
    pin_observed_claims: bool = False


class FleetPolicyPresetApply(BaseModel):
    """Apply an integrity-policy preset to some or all agents."""

    preset: IntegrityPreset = IntegrityPreset.standard
    agent_ids: list[str] = Field(default_factory=list)
    pin_observed_claims: bool = False


class AgentStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    degraded = "degraded"


class IntegrityAssessment(BaseModel):
    status: IntegrityStatus = IntegrityStatus.unknown
    score: int = 50
    reasons: list[str] = Field(default_factory=list)
    last_evaluated: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AgentTelemetry(BaseModel):
    """Telemetry signals emitted by sidecars/sensors for integrity checks."""

    agent_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    probe_source: TelemetryProbeSource = TelemetryProbeSource.sidecar
    telemetry_mode: TelemetryMode = TelemetryMode.sidecar_only
    network_rtt_ms: float | None = None
    network_jitter_ms: float | None = None
    is_remote_session: bool = False
    observed_provider: str | None = None
    observed_model: str | None = None
    observed_region: str | None = None
    sensor_hid_rtt_ms: float | None = None
    sensor_dwell_ms: float | None = None
    sensor_os_jitter_ms: float | None = None
    detail: str | None = None


class AgentRecord(BaseModel):
    """Internal record of a registered agent."""

    agent_id: str
    display_name: str
    status: AgentStatus = AgentStatus.inactive
    policy: AgentPolicy
    registered_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_heartbeat: str | None = None
    last_event: str | None = None
    last_telemetry: str | None = None
    integrity: IntegrityAssessment = Field(default_factory=IntegrityAssessment)
    observed_provider: str | None = None
    observed_model: str | None = None
    observed_region: str | None = None
    last_probe_source: TelemetryProbeSource | None = None
    last_telemetry_mode: TelemetryMode | None = None
    last_network_rtt_ms: float | None = None
    last_network_jitter_ms: float | None = None
    last_sensor_hid_rtt_ms: float | None = None
    last_sensor_dwell_ms: float | None = None
    last_sensor_os_jitter_ms: float | None = None
    token: str = ""  # sidecar auth token


class AgentStore(BaseModel):
    """Persisted agent registry."""

    agents: dict[str, AgentRecord] = Field(default_factory=dict)


class EventStore(BaseModel):
    """Persisted event log."""

    events: list[AgentEvent] = Field(default_factory=list)


class TelemetryStore(BaseModel):
    """Persisted telemetry signal stream."""

    telemetry: list[AgentTelemetry] = Field(default_factory=list)
