"""Tests for agent CRUD: register, list, get, deregister, re-register."""


def test_register_agent(client, admin_headers):
    resp = client.post(
        "/api/v1/agents",
        json={"agent_id": "a1", "display_name": "Agent One", "tier": "L1"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["existing"] is False
    assert data["agent_id"] == "a1"
    assert data["token"].startswith("swb_sk_")


def test_register_duplicate_returns_existing(client, admin_headers):
    payload = {"agent_id": "dup", "display_name": "Dup"}
    resp1 = client.post("/api/v1/agents", json=payload, headers=admin_headers)
    resp2 = client.post("/api/v1/agents", json=payload, headers=admin_headers)
    assert resp2.json()["existing"] is True
    assert resp2.json()["token"] == resp1.json()["token"]


def test_list_agents(client, admin_headers, registered_agent):
    resp = client.get("/api/v1/agents", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert len(data["agents"]) == 1
    assert data["agents"][0]["agent_id"] == "test-agent"


def test_get_agent(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    resp = client.get(f"/api/v1/agents/{agent_id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["agent_id"] == agent_id
    assert data["display_name"] == "Test Agent"


def test_get_unknown_agent_404(client, admin_headers):
    resp = client.get("/api/v1/agents/nonexistent", headers=admin_headers)
    assert resp.status_code == 404


def test_deregister_agent(client, admin_headers, registered_agent):
    agent_id, _ = registered_agent
    resp = client.delete(f"/api/v1/agents/{agent_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["deregistered"] is True

    resp2 = client.get(f"/api/v1/agents/{agent_id}", headers=admin_headers)
    assert resp2.status_code == 404


def test_deregister_unknown_404(client, admin_headers):
    resp = client.delete("/api/v1/agents/ghost", headers=admin_headers)
    assert resp.status_code == 404
