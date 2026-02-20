"""Tests for policy updates, presets, fleet-wide preset application."""


def test_update_policy_tier(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    resp = client.put(
        f"/api/v1/agents/{agent_id}/policy",
        json={"tier": "L2"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["policy"]["tier"] == "L2"
    assert data["policy"]["version"] == 2


def test_update_policy_increments_version(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    client.put(
        f"/api/v1/agents/{agent_id}/policy",
        json={"tier": "L2"},
        headers=admin_headers,
    )
    resp = client.put(
        f"/api/v1/agents/{agent_id}/policy",
        json={"allowed_actions": ["read", "write"]},
        headers=admin_headers,
    )
    assert resp.json()["policy"]["version"] == 3


def test_update_policy_unknown_agent_404(client, admin_headers):
    resp = client.put(
        "/api/v1/agents/ghost/policy",
        json={"tier": "L3"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_list_presets(client):
    resp = client.get("/api/v1/policy/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    names = [p["name"] for p in data["presets"]]
    assert "standard" in names
    assert "strict" in names
    assert "relaxed" in names


def test_preset_standard_thresholds(client):
    resp = client.get("/api/v1/policy/presets")
    presets = {p["name"]: p for p in resp.json()["presets"]}
    std = presets["standard"]["integrity"]
    assert std["max_network_rtt_ms"] == 120.0
    assert std["max_network_jitter_ms"] == 30.0
    assert std["allow_remote_session"] is False


def test_preset_strict_thresholds(client):
    resp = client.get("/api/v1/policy/presets")
    presets = {p["name"]: p for p in resp.json()["presets"]}
    strict = presets["strict"]["integrity"]
    assert strict["max_network_rtt_ms"] == 70.0
    assert strict["max_network_jitter_ms"] == 18.0


def test_preset_relaxed_allows_remote(client):
    resp = client.get("/api/v1/policy/presets")
    presets = {p["name"]: p for p in resp.json()["presets"]}
    relaxed = presets["relaxed"]["integrity"]
    assert relaxed["allow_remote_session"] is True
    assert relaxed["max_network_rtt_ms"] == 240.0


def test_apply_preset_to_agent(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    resp = client.post(
        f"/api/v1/agents/{agent_id}/policy/preset",
        json={"preset": "strict"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["preset"] == "strict"
    assert data["policy"]["integrity"]["max_network_rtt_ms"] == 70.0


def test_apply_preset_unknown_agent_404(client, admin_headers):
    resp = client.post(
        "/api/v1/agents/ghost/policy/preset",
        json={"preset": "standard"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_fleet_preset_applies_to_all(client, admin_headers):
    # Register two agents
    client.post(
        "/api/v1/agents",
        json={"agent_id": "a1", "display_name": "A1"},
        headers=admin_headers,
    )
    client.post(
        "/api/v1/agents",
        json={"agent_id": "a2", "display_name": "A2"},
        headers=admin_headers,
    )

    resp = client.post(
        "/api/v1/fleet/policy/preset",
        json={"preset": "strict"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["applied"] == 2
    assert data["missing"] == []


def test_fleet_preset_reports_missing(client, admin_headers):
    client.post(
        "/api/v1/agents",
        json={"agent_id": "a1"},
        headers=admin_headers,
    )
    resp = client.post(
        "/api/v1/fleet/policy/preset",
        json={"preset": "standard", "agent_ids": ["a1", "ghost"]},
        headers=admin_headers,
    )
    data = resp.json()
    assert data["applied"] == 1
    assert "ghost" in data["missing"]


def test_apply_preset_pin_observed_claims(client, admin_headers):
    # Register agent and send telemetry so it has observed claims
    resp = client.post(
        "/api/v1/agents",
        json={"agent_id": "pin-test"},
        headers=admin_headers,
    )
    token = resp.json()["token"]

    # Send telemetry with observed claims
    client.post(
        "/api/v1/telemetry",
        json={
            "agent_id": "pin-test",
            "observed_provider": "anthropic",
            "observed_model": "claude-3",
            "observed_region": "us-east-1",
            "network_rtt_ms": 5.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Apply preset with pin
    resp = client.post(
        "/api/v1/agents/pin-test/policy/preset",
        json={"preset": "standard", "pin_observed_claims": True},
        headers=admin_headers,
    )
    data = resp.json()
    assert data["ok"] is True
    integrity = data["policy"]["integrity"]
    assert "anthropic" in integrity["expected_providers"]
    assert "claude-3" in integrity["expected_models"]
    assert "us-east-1" in integrity["expected_regions"]
