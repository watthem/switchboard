"""Tests for file-backed JSON storage: persistence, trimming, corrupt recovery."""

from herald.v1.models import AgentEvent, AgentStore, AgentTelemetry, EventStore, TelemetryStore
from herald.v1 import services


def test_agents_persist_across_load_save(tmp_path):
    """Data survives a save/load cycle."""
    from herald.v1.models import AgentPolicy, AgentRecord

    store = AgentStore()
    store.agents["a1"] = AgentRecord(
        agent_id="a1",
        display_name="Agent One",
        policy=AgentPolicy(agent_id="a1"),
        token="hld_sk_test",
    )
    services._save_agents(store)

    loaded = services._load_agents()
    assert "a1" in loaded.agents
    assert loaded.agents["a1"].display_name == "Agent One"
    assert loaded.agents["a1"].token == "hld_sk_test"


def test_events_persist_across_load_save():
    store = EventStore()
    store.events.append(
        AgentEvent(agent_id="a1", action="read", target="/tmp")
    )
    services._save_events(store)

    loaded = services._load_events()
    assert len(loaded.events) == 1
    assert loaded.events[0].action == "read"


def test_telemetry_persist_across_load_save():
    store = TelemetryStore()
    store.telemetry.append(
        AgentTelemetry(agent_id="a1", network_rtt_ms=5.0)
    )
    services._save_telemetry(store)

    loaded = services._load_telemetry()
    assert len(loaded.telemetry) == 1
    assert loaded.telemetry[0].network_rtt_ms == 5.0


def test_events_trimmed_at_max(monkeypatch):
    """Events beyond _MAX_EVENTS are trimmed to keep the most recent."""
    monkeypatch.setattr(services, "_MAX_EVENTS", 5)

    store = EventStore()
    for i in range(10):
        store.events.append(
            AgentEvent(agent_id="a1", action=f"action_{i}", target="t")
        )
    services._save_events(store)

    loaded = services._load_events()
    assert len(loaded.events) == 5
    # Most recent kept (last 5)
    assert loaded.events[0].action == "action_5"
    assert loaded.events[-1].action == "action_9"


def test_telemetry_trimmed_at_max(monkeypatch):
    monkeypatch.setattr(services, "_MAX_TELEMETRY", 3)

    store = TelemetryStore()
    for i in range(7):
        store.telemetry.append(
            AgentTelemetry(agent_id="a1", network_rtt_ms=float(i))
        )
    services._save_telemetry(store)

    loaded = services._load_telemetry()
    assert len(loaded.telemetry) == 3
    assert loaded.telemetry[0].network_rtt_ms == 4.0


def test_corrupt_agents_json_returns_empty():
    """Corrupt JSON gracefully returns empty store."""
    services._ensure_data_dir()
    services._AGENTS_FILE.write_text("{invalid json", encoding="utf-8")

    loaded = services._load_agents()
    assert loaded.agents == {}


def test_corrupt_events_json_returns_empty():
    services._ensure_data_dir()
    services._EVENTS_FILE.write_text("not json at all", encoding="utf-8")

    loaded = services._load_events()
    assert loaded.events == []


def test_corrupt_telemetry_json_returns_empty():
    services._ensure_data_dir()
    services._TELEMETRY_FILE.write_text("[broken", encoding="utf-8")

    loaded = services._load_telemetry()
    assert loaded.telemetry == []


def test_missing_file_returns_empty():
    """Non-existent files return empty stores (no crash)."""
    assert services._load_agents().agents == {}
    assert services._load_events().events == []
    assert services._load_telemetry().telemetry == []
