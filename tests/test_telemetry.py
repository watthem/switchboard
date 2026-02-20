"""Tests for telemetry ingestion, integrity scoring via API, fleet telemetry."""


def test_ingest_telemetry(client, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    resp = client.post(
        "/api/v1/telemetry",
        json={
            "agent_id": agent_id,
            "network_rtt_ms": 5.0,
            "network_jitter_ms": 1.0,
            "observed_provider": "anthropic",
        },
        headers=bearer_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["integrity_score"] == 100
    assert data["integrity_status"] == "normal"


def test_telemetry_updates_agent_record(client, admin_headers, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    client.post(
        "/api/v1/telemetry",
        json={
            "agent_id": agent_id,
            "network_rtt_ms": 3.0,
            "observed_provider": "anthropic",
            "observed_model": "claude-3",
            "probe_source": "hook",
        },
        headers=bearer_headers,
    )

    resp = client.get(f"/api/v1/agents/{agent_id}", headers=admin_headers)
    data = resp.json()
    assert data["observed_provider"] == "anthropic"
    assert data["observed_model"] == "claude-3"
    assert data["last_probe_source"] == "hook"
    assert data["last_network_rtt_ms"] == 3.0


def test_telemetry_high_rtt_lowers_score(client, admin_headers, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    # Set a policy with RTT limit
    client.put(
        f"/api/v1/agents/{agent_id}/policy",
        json={"integrity": {"max_network_rtt_ms": 50.0}},
        headers=admin_headers,
    )

    resp = client.post(
        "/api/v1/telemetry",
        json={
            "agent_id": agent_id,
            "network_rtt_ms": 80.0,
        },
        headers=bearer_headers,
    )
    data = resp.json()
    assert data["integrity_score"] < 100
    assert any("rtt" in r for r in data["integrity_reasons"])


def test_query_telemetry_requires_admin(client, bearer_headers):
    resp = client.get("/api/v1/telemetry")
    assert resp.status_code == 401


def test_query_telemetry_with_admin(client, admin_headers, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    client.post(
        "/api/v1/telemetry",
        json={"agent_id": agent_id, "network_rtt_ms": 5.0},
        headers=bearer_headers,
    )

    resp = client.get("/api/v1/telemetry", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1


def test_fleet_telemetry_timeline(client, admin_headers, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    for rtt in [5.0, 10.0, 15.0]:
        client.post(
            "/api/v1/telemetry",
            json={"agent_id": agent_id, "network_rtt_ms": rtt},
            headers=bearer_headers,
        )

    resp = client.get("/api/v1/fleet/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert data["summary"]["metrics"]["network_rtt_ms"] is not None
    scorecard = data["summary"]["metrics"]["network_rtt_ms"]
    assert "p50" in scorecard
    assert "p95" in scorecard
    assert scorecard["min"] == 5.0
    assert scorecard["max"] == 15.0


def test_fleet_telemetry_filter_by_agent(client, admin_headers):
    # Register two agents and send telemetry for each
    r1 = client.post(
        "/api/v1/agents", json={"agent_id": "a1"}, headers=admin_headers
    )
    r2 = client.post(
        "/api/v1/agents", json={"agent_id": "a2"}, headers=admin_headers
    )
    t1 = r1.json()["token"]
    t2 = r2.json()["token"]

    client.post(
        "/api/v1/telemetry",
        json={"agent_id": "a1", "network_rtt_ms": 5.0},
        headers={"Authorization": f"Bearer {t1}"},
    )
    client.post(
        "/api/v1/telemetry",
        json={"agent_id": "a2", "network_rtt_ms": 10.0},
        headers={"Authorization": f"Bearer {t2}"},
    )

    resp = client.get("/api/v1/fleet/telemetry", params={"agent_id": "a1"})
    assert resp.json()["count"] == 1


def test_ingest_telemetry_unknown_agent_404(client, bearer_headers):
    resp = client.post(
        "/api/v1/telemetry",
        json={"agent_id": "nonexistent", "network_rtt_ms": 5.0},
        headers=bearer_headers,
    )
    # Token won't match nonexistent agent
    assert resp.status_code == 403
