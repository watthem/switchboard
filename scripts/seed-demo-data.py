#!/usr/bin/env python3
"""Seed Switchboard with demo agents and telemetry for screenshots.

Usage:
    SWITCHBOARD_API_KEY=demo-key python3 scripts/seed-demo-data.py
"""

import os
import sys
import time

import httpx

BASE = os.getenv("SWITCHBOARD_URL", "http://localhost:59237")
KEY = os.getenv("SWITCHBOARD_API_KEY", "")
HEADERS = {"X-Switchboard-Key": KEY} if KEY else {}

AGENTS = [
    {
        "agent_id": "harold",
        "display_name": "Harold",
        "tier": "L1",
        "allowed_actions": ["check_calendar", "read_email", "send_reminder"],
        "channels": ["household"],
    },
    {
        "agent_id": "director",
        "display_name": "Director",
        "tier": "L1",
        "allowed_actions": ["read_portfolio", "draft_content", "publish_review"],
        "channels": ["editorial"],
    },
    {
        "agent_id": "gruly",
        "display_name": "Gruly",
        "tier": "L2",
        "allowed_actions": ["file_read", "file_write", "git_commit", "run_tests"],
        "channels": ["engineering"],
    },
    {
        "agent_id": "claude-code",
        "display_name": "Claude Code",
        "tier": "L2",
        "allowed_actions": ["file_read", "file_write", "bash_exec", "git_commit"],
        "channels": ["engineering"],
    },
]

TELEMETRY = [
    # Harold — local, low latency, perfect score
    {"agent_id": "harold", "network_rtt_ms": 1.8, "network_jitter_ms": 0.3,
     "observed_provider": "anthropic", "observed_model": "claude-haiku",
     "observed_region": "local", "probe_source": "sidecar"},
    # Director — local, slightly higher latency
    {"agent_id": "director", "network_rtt_ms": 2.1, "network_jitter_ms": 0.5,
     "observed_provider": "anthropic", "observed_model": "claude-sonnet",
     "observed_region": "local", "probe_source": "sidecar"},
    # Gruly — local, good latency
    {"agent_id": "gruly", "network_rtt_ms": 1.5, "network_jitter_ms": 0.2,
     "observed_provider": "anthropic", "observed_model": "claude-haiku",
     "observed_region": "local", "probe_source": "sidecar"},
    # Claude Code — hook-based, very fast
    {"agent_id": "claude-code", "network_rtt_ms": 1.2, "network_jitter_ms": 0.1,
     "observed_provider": "anthropic", "observed_model": "claude-opus",
     "observed_region": "local", "probe_source": "hook"},
]

EVENTS = [
    {"agent_id": "harold", "action": "check_calendar", "target": "family-calendar", "result": "success"},
    {"agent_id": "harold", "action": "send_reminder", "target": "grocery-list", "result": "success"},
    {"agent_id": "director", "action": "read_portfolio", "target": "Q1-review", "result": "success"},
    {"agent_id": "director", "action": "draft_content", "target": "blog-post-draft", "result": "success"},
    {"agent_id": "gruly", "action": "file_read", "target": "/src/main.rs", "result": "success"},
    {"agent_id": "gruly", "action": "git_commit", "target": "feature/auth", "result": "success"},
    {"agent_id": "gruly", "action": "run_tests", "target": "cargo test", "result": "success"},
    {"agent_id": "claude-code", "action": "file_write", "target": "tests/conftest.py", "result": "success"},
    {"agent_id": "claude-code", "action": "bash_exec", "target": "pytest tests/ -v", "result": "success"},
    {"agent_id": "claude-code", "action": "git_commit", "target": "main", "result": "success"},
]


def main():
    # Health check
    try:
        r = httpx.get(f"{BASE}/health", timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"Switchboard not reachable at {BASE}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Connected to Switchboard at {BASE}")

    # Register agents
    tokens = {}
    for agent in AGENTS:
        r = httpx.post(f"{BASE}/api/v1/agents", json=agent, headers=HEADERS)
        data = r.json()
        tokens[agent["agent_id"]] = data["token"]
        status = "existing" if data.get("existing") else "registered"
        print(f"  {status}: {agent['agent_id']} (tier={agent['tier']})")

    # Apply standard preset to all
    httpx.post(
        f"{BASE}/api/v1/fleet/policy/preset",
        json={"preset": "standard"},
        headers=HEADERS,
    )
    print("  Applied 'standard' preset to fleet")

    # Send telemetry (multiple rounds for timeline data)
    for round_num in range(3):
        for t in TELEMETRY:
            bearer = {"Authorization": f"Bearer {tokens[t['agent_id']]}"}
            httpx.post(f"{BASE}/api/v1/telemetry", json=t, headers=bearer)
        if round_num < 2:
            time.sleep(0.1)  # tiny gap for timestamp variety

    print(f"  Sent {len(TELEMETRY) * 3} telemetry samples")

    # Send events
    for event in EVENTS:
        bearer = {"Authorization": f"Bearer {tokens[event['agent_id']]}"}
        httpx.post(f"{BASE}/api/v1/events", json=event, headers=bearer)

    print(f"  Sent {len(EVENTS)} events")

    # Send heartbeats to make agents active
    for agent_id, token in tokens.items():
        bearer = {"Authorization": f"Bearer {token}"}
        httpx.post(
            f"{BASE}/api/v1/events",
            json={"agent_id": agent_id, "action": "heartbeat", "target": "self"},
            headers=bearer,
        )

    print(f"  Sent heartbeats for {len(tokens)} agents")
    print("\nDone. Dashboard should show 4 active agents with integrity data.")


if __name__ == "__main__":
    main()
