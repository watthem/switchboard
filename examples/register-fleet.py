#!/usr/bin/env python3
"""Register example agents with Switchboard v1.

Demonstrates fleet registration. Adapt FLEET list for your agents.

Usage:
    SWITCHBOARD_API_KEY=your-key python examples/register-fleet.py
"""

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SWITCHBOARD_URL = os.getenv("SWITCHBOARD_URL", "http://localhost:59237")
ADMIN_KEY = os.getenv("SWITCHBOARD_API_KEY", "")

# Example agents — replace with your fleet
FLEET = [
    {
        "agent_id": "agent-alpha",
        "display_name": "Agent Alpha — Data Analyst",
        "tier": "L1",
        "allowed_actions": [
            "read_data", "query_api", "send_notification",
        ],
        "denied_actions": ["write_files", "access_network", "manage_credentials"],
        "channels": ["ops", "alerts"],
    },
    {
        "agent_id": "agent-beta",
        "display_name": "Agent Beta — Ops Automation",
        "tier": "L2",
        "allowed_actions": [
            "read_data", "write_files", "execute_commands",
            "send_notification",
        ],
        "denied_actions": ["manage_credentials", "delete_data"],
        "channels": ["ops", "engineering"],
    },
    {
        "agent_id": "agent-gamma",
        "display_name": "Agent Gamma — Observer",
        "tier": "L0",
        "allowed_actions": ["read_data"],
        "denied_actions": [
            "write_files", "access_network", "manage_credentials",
            "send_notification",
        ],
        "channels": ["monitoring"],
    },
]


def register(agent: dict) -> str | None:
    """Register an agent, return token."""
    headers = {"Content-Type": "application/json"}
    if ADMIN_KEY:
        headers["X-Switchboard-Key"] = ADMIN_KEY

    data = json.dumps(agent).encode()
    req = Request(
        f"{SWITCHBOARD_URL}/api/v1/agents",
        data=data, headers=headers, method="POST",
    )

    try:
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                return result["token"]
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  Error {e.code}: {body[:200]}")
    except Exception as e:
        print(f"  Failed: {e}")

    return None


def main():
    print(f"Registering example fleet with Switchboard at {SWITCHBOARD_URL}\n")

    tokens = {}
    for agent in FLEET:
        agent_id = agent["agent_id"]
        print(f"Registering {agent_id}...")
        token = register(agent)
        if token:
            tokens[agent_id] = token
            print(f"  OK — token: {token[:20]}...")
        else:
            print(f"  FAILED — no token")

    print(f"\n{'='*60}")
    print("Fleet registration complete.\n")

    print("Environment variables for each agent's sidecar:\n")
    for agent_id, token in tokens.items():
        print(f"  {agent_id}:")
        print(f"    SWITCHBOARD_AGENT_ID={agent_id}")
        print(f"    SWITCHBOARD_SIDECAR_TOKEN={token}")
        print()

    print(f"Verify: curl {SWITCHBOARD_URL}/api/v1/fleet/status | python3 -m json.tool")
    print(f"Dashboard: {SWITCHBOARD_URL}/dashboard")


if __name__ == "__main__":
    main()
