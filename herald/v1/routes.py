"""Herald v1 API routes — governance protocol endpoints.

Mount on the main FastAPI app as a sub-router under /api/v1.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from .models import (
    AgentEvent,
    AgentRegistration,
    AgentTelemetry,
    FleetPolicyPresetApply,
    PolicyPresetApply,
    PolicyUpdate,
)
from . import services

logger = logging.getLogger("herald.v1.routes")

router = APIRouter(prefix="/api/v1", tags=["v1"])

# --- Auth ---

_admin_key_header = APIKeyHeader(name="X-Herald-Key", auto_error=False)
_bearer = HTTPBearer(auto_error=False)


async def _require_admin(api_key: str | None = Depends(_admin_key_header)) -> str:
    """Admin auth — uses the same X-Herald-Key as legacy endpoints."""
    expected = os.getenv("HERALD_API_KEY", "").strip()
    if not expected:
        return ""  # dev mode
    if not api_key or api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")
    return api_key


async def _require_sidecar(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Sidecar auth — Bearer token issued during registration."""
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing sidecar bearer token")
    return creds.credentials


# --- Agent management (admin) ---


@router.post("/agents")
async def register_agent(
    reg: AgentRegistration, _key: str = Depends(_require_admin)
):
    result = services.register_agent(reg)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["error"])
    return result


@router.get("/agents")
async def list_agents(_key: str = Depends(_require_admin)):
    return services.list_agents()


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, _key: str = Depends(_require_admin)):
    result = services.get_agent(agent_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/agents/{agent_id}/policy")
async def get_agent_policy(agent_id: str, token: str = Depends(_require_sidecar)):
    """Get agent policy — called by sidecar with its bearer token."""
    if not services.validate_token(agent_id, token):
        raise HTTPException(status_code=403, detail="Token not valid for this agent")
    return services.get_agent_policy(agent_id)


@router.put("/agents/{agent_id}/policy")
async def update_policy(
    agent_id: str, update: PolicyUpdate, _key: str = Depends(_require_admin)
):
    result = services.update_policy(agent_id, update)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/policy/presets")
async def list_policy_presets():
    """Built-in integrity-policy presets for dashboard/admin UX."""
    return services.list_policy_presets()


@router.post("/agents/{agent_id}/policy/preset")
async def apply_policy_preset(
    agent_id: str,
    req: PolicyPresetApply,
    _key: str = Depends(_require_admin),
):
    result = services.apply_policy_preset(
        agent_id=agent_id,
        preset=req.preset.value,
        pin_observed_claims=req.pin_observed_claims,
    )
    if not result["ok"]:
        if "not found" in result.get("error", "").lower():
            raise HTTPException(status_code=404, detail=result["error"])
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/fleet/policy/preset")
async def apply_fleet_policy_preset(
    req: FleetPolicyPresetApply,
    _key: str = Depends(_require_admin),
):
    result = services.apply_policy_preset_fleet(
        preset=req.preset.value,
        agent_ids=req.agent_ids,
        pin_observed_claims=req.pin_observed_claims,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/agents/{agent_id}")
async def deregister_agent(agent_id: str, _key: str = Depends(_require_admin)):
    result = services.deregister_agent(agent_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# --- Event ingestion (sidecar) ---


@router.post("/events")
async def ingest_event(event: AgentEvent, token: str = Depends(_require_sidecar)):
    """Receive an event from a sidecar. Validates token against agent_id."""
    if not services.validate_token(event.agent_id, token):
        raise HTTPException(
            status_code=403, detail="Token not valid for this agent"
        )
    return services.ingest_event(event)


@router.post("/telemetry")
async def ingest_telemetry(
    telemetry: AgentTelemetry, token: str = Depends(_require_sidecar)
):
    """Receive telemetry signals from sidecar/sensor path."""
    if not services.validate_token(telemetry.agent_id, token):
        raise HTTPException(
            status_code=403, detail="Token not valid for this agent"
        )
    result = services.ingest_telemetry(telemetry)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# --- Audit log (admin) ---


@router.get("/events")
async def query_events(
    agent_id: str | None = Query(None),
    action: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    return services.query_events(
        agent_id=agent_id, action=action, since=since, limit=limit
    )


@router.get("/telemetry")
async def query_telemetry(
    agent_id: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    _key: str = Depends(_require_admin),
):
    return services.query_telemetry(agent_id=agent_id, since=since, limit=limit)


# --- Fleet status (public, read-only) ---


@router.get("/fleet/telemetry")
async def fleet_telemetry_endpoint(
    agent_id: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
):
    return services.fleet_telemetry(agent_id=agent_id, since=since, limit=limit)


@router.get("/fleet/status")
async def fleet_status_endpoint():
    return services.fleet_status()


@router.get("/fleet/health")
async def fleet_health_endpoint():
    return services.fleet_health()
