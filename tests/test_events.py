"""Tests for event ingestion, audit log queries, heartbeat handling."""


def test_ingest_event(client, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    resp = client.post(
        "/api/v1/events",
        json={
            "agent_id": agent_id,
            "action": "file_read",
            "target": "/etc/hosts",
        },
        headers=bearer_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "event_id" in data


def test_heartbeat_updates_agent(client, admin_headers, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    client.post(
        "/api/v1/events",
        json={
            "agent_id": agent_id,
            "action": "heartbeat",
            "target": "self",
        },
        headers=bearer_headers,
    )

    resp = client.get(f"/api/v1/agents/{agent_id}", headers=admin_headers)
    data = resp.json()
    assert data["last_heartbeat"] is not None
    assert data["status"] == "active"


def test_query_events_most_recent_first(client, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    for i in range(3):
        client.post(
            "/api/v1/events",
            json={
                "agent_id": agent_id,
                "action": f"action_{i}",
                "target": "t",
            },
            headers=bearer_headers,
        )

    resp = client.get("/api/v1/events")
    data = resp.json()
    assert data["count"] == 3
    # Most recent first
    assert data["events"][0]["action"] == "action_2"


def test_query_events_filter_by_agent(client, admin_headers, bearer_headers, registered_agent):
    agent_id, _ = registered_agent
    # Register a second agent
    resp = client.post(
        "/api/v1/agents",
        json={"agent_id": "other"},
        headers=admin_headers,
    )
    other_token = resp.json()["token"]

    client.post(
        "/api/v1/events",
        json={"agent_id": agent_id, "action": "read", "target": "t"},
        headers=bearer_headers,
    )
    client.post(
        "/api/v1/events",
        json={"agent_id": "other", "action": "write", "target": "t"},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    resp = client.get("/api/v1/events", params={"agent_id": agent_id})
    assert resp.json()["count"] == 1
    assert resp.json()["events"][0]["agent_id"] == agent_id


def test_query_events_filter_by_action(client, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    client.post(
        "/api/v1/events",
        json={"agent_id": agent_id, "action": "read", "target": "t"},
        headers=bearer_headers,
    )
    client.post(
        "/api/v1/events",
        json={"agent_id": agent_id, "action": "write", "target": "t"},
        headers=bearer_headers,
    )

    resp = client.get("/api/v1/events", params={"action": "write"})
    assert resp.json()["count"] == 1


def test_query_events_limit(client, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    for i in range(5):
        client.post(
            "/api/v1/events",
            json={"agent_id": agent_id, "action": f"a{i}", "target": "t"},
            headers=bearer_headers,
        )

    resp = client.get("/api/v1/events", params={"limit": 2})
    assert resp.json()["count"] == 2


def test_non_heartbeat_event_updates_last_event(client, admin_headers, registered_agent, bearer_headers):
    agent_id, _ = registered_agent
    client.post(
        "/api/v1/events",
        json={"agent_id": agent_id, "action": "file_read", "target": "/tmp/x"},
        headers=bearer_headers,
    )
    resp = client.get(f"/api/v1/agents/{agent_id}", headers=admin_headers)
    assert resp.json()["last_event"] is not None
