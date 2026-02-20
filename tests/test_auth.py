"""Tests for auth: admin key enforcement, sidecar tokens, dev mode."""


def test_admin_endpoint_requires_key(client, admin_key):
    """Admin endpoints return 401 without key when HERALD_API_KEY is set."""
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 401


def test_admin_endpoint_wrong_key(client, admin_key):
    resp = client.get("/api/v1/agents", headers={"X-Herald-Key": "wrong"})
    assert resp.status_code == 401


def test_admin_endpoint_correct_key(client, admin_headers):
    resp = client.get("/api/v1/agents", headers=admin_headers)
    assert resp.status_code == 200


def test_dev_mode_no_key_required(client, monkeypatch):
    """When HERALD_API_KEY is unset, admin endpoints work without auth."""
    monkeypatch.delenv("HERALD_API_KEY", raising=False)
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200


def test_sidecar_endpoint_requires_bearer(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    resp = client.post(
        "/api/v1/events",
        json={"agent_id": agent_id, "action": "test", "target": "t"},
    )
    assert resp.status_code == 401


def test_sidecar_wrong_token_403(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    resp = client.post(
        "/api/v1/events",
        json={"agent_id": agent_id, "action": "test", "target": "t"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 403


def test_sidecar_correct_token(client, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    resp = client.post(
        "/api/v1/events",
        json={"agent_id": agent_id, "action": "test", "target": "t"},
        headers=bearer_headers,
    )
    assert resp.status_code == 200


def test_policy_fetch_requires_sidecar_token(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    resp = client.get(f"/api/v1/agents/{agent_id}/policy")
    assert resp.status_code == 401


def test_policy_fetch_wrong_token_403(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    resp = client.get(
        f"/api/v1/agents/{agent_id}/policy",
        headers={"Authorization": "Bearer bad"},
    )
    assert resp.status_code == 403


def test_policy_fetch_correct_token(client, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    resp = client.get(
        f"/api/v1/agents/{agent_id}/policy",
        headers=bearer_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == agent_id
    assert data["tier"] == "L1"


def test_telemetry_endpoint_requires_bearer(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    resp = client.post(
        "/api/v1/telemetry",
        json={"agent_id": agent_id, "network_rtt_ms": 5.0},
    )
    assert resp.status_code == 401


def test_public_endpoints_no_auth(client):
    """Public endpoints work without any auth."""
    assert client.get("/api/v1/policy/presets").status_code == 200
    assert client.get("/api/v1/events").status_code == 200
    assert client.get("/api/v1/fleet/status").status_code == 200
    assert client.get("/api/v1/fleet/health").status_code == 200
    assert client.get("/api/v1/fleet/telemetry").status_code == 200
