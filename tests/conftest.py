"""Shared fixtures for Switchboard test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ADMIN_KEY = "test-admin-key-abc123"


@pytest.fixture(autouse=True)
def _isolate_storage(monkeypatch, tmp_path):
    """Redirect all file-backed storage to a temp directory per test."""
    import switchboard.v1.services as svc

    data_dir = tmp_path / "data" / "v1"
    monkeypatch.setattr(svc, "_DATA_DIR", data_dir)
    monkeypatch.setattr(svc, "_AGENTS_FILE", data_dir / "agents.json")
    monkeypatch.setattr(svc, "_EVENTS_FILE", data_dir / "events.json")
    monkeypatch.setattr(svc, "_TELEMETRY_FILE", data_dir / "telemetry.json")


@pytest.fixture
def admin_key(monkeypatch):
    """Set SWITCHBOARD_API_KEY and return the key string."""
    monkeypatch.setenv("SWITCHBOARD_API_KEY", ADMIN_KEY)
    return ADMIN_KEY


@pytest.fixture
def admin_headers(admin_key):
    """Headers dict with X-Switchboard-Key for admin endpoints."""
    return {"X-Switchboard-Key": admin_key}


@pytest.fixture
def client():
    """FastAPI TestClient with isolated storage (via autouse fixture)."""
    from switchboard.app import create_app

    return TestClient(create_app())


@pytest.fixture
def registered_agent(client, admin_headers):
    """Register a test agent and return (agent_id, token)."""
    resp = client.post(
        "/api/v1/agents",
        json={"agent_id": "test-agent", "display_name": "Test Agent", "tier": "L1"},
        headers=admin_headers,
    )
    data = resp.json()
    return data["agent_id"], data["token"]


@pytest.fixture
def bearer_headers(registered_agent):
    """Headers dict with Bearer token for sidecar endpoints."""
    _, token = registered_agent
    return {"Authorization": f"Bearer {token}"}
