#!/usr/bin/env python3
"""Herald Sidecar — connects any agent to the Herald governance protocol.

Zero external dependencies. Runs alongside your agent container.

Usage:
    # With config file:
    python herald-sidecar.py --config herald-sidecar.yaml

    # With environment variables:
    HERALD_URL=http://herald:59237 AGENT_ID=my-agent python herald-sidecar.py

    # Register a new agent (prints token):
    python herald-sidecar.py --register --tier L1

What it does:
    1. Registers with Herald (or uses existing token)
    2. Pulls policy and writes it locally for your agent to read
    3. Listens on localhost:9100 for events from your agent
    4. Forwards events to Herald with auth
    5. Sends heartbeats every 30s
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from statistics import pstdev
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [sidecar] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sidecar")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load config from YAML file, env vars, or CLI args."""
    config = {
        "herald_url": os.getenv("HERALD_URL", "http://localhost:59237"),
        "agent_id": os.getenv("AGENT_ID", ""),
        "sidecar_token": os.getenv("SIDECAR_TOKEN", ""),
        "admin_key": os.getenv("HERALD_API_KEY", ""),
        "policy_format": os.getenv("POLICY_FORMAT", "json"),
        "policy_path": os.getenv("POLICY_PATH", "/herald/policy.json"),
        "event_listen_port": int(os.getenv("EVENT_LISTEN_PORT", "9100")),
        "heartbeat_interval": int(os.getenv("HEARTBEAT_INTERVAL", "30")),
        "tier": os.getenv("AGENT_TIER", "L0"),
        "display_name": os.getenv("AGENT_DISPLAY_NAME", ""),
        "allowed_actions": os.getenv("ALLOWED_ACTIONS", ""),
        "channels": os.getenv("AGENT_CHANNELS", ""),
        "telemetry_interval": int(
            os.getenv("TELEMETRY_INTERVAL", os.getenv("HEARTBEAT_INTERVAL", "30"))
        ),
        "telemetry_mode": os.getenv("TELEMETRY_MODE", "sidecar_only"),
        "observed_provider": os.getenv("OBSERVED_PROVIDER", ""),
        "observed_model": os.getenv("OBSERVED_MODEL", ""),
        "observed_region": os.getenv("OBSERVED_REGION", ""),
        "remote_session_hint": os.getenv("REMOTE_SESSION_HINT", ""),
        "sensor_hid_rtt_ms": os.getenv("SENSOR_HID_RTT_MS", ""),
        "sensor_dwell_ms": os.getenv("SENSOR_DWELL_MS", ""),
        "sensor_os_jitter_ms": os.getenv("SENSOR_OS_JITTER_MS", ""),
    }

    # Try loading YAML config if specified
    config_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--config" and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]

    if config_path and Path(config_path).exists():
        try:
            import yaml
            with open(config_path) as f:
                file_config = yaml.safe_load(f) or {}
            # File config overrides defaults, env vars override file config
            for key, val in file_config.items():
                env_key = key.upper()
                if not os.getenv(env_key):
                    config[key] = val
        except ImportError:
            # No PyYAML — try JSON
            with open(config_path) as f:
                file_config = json.load(f)
            for key, val in file_config.items():
                env_key = key.upper()
                if not os.getenv(env_key):
                    config[key] = val

    # CLI overrides
    for i, arg in enumerate(sys.argv):
        if arg == "--tier" and i + 1 < len(sys.argv):
            config["tier"] = sys.argv[i + 1]
        elif arg == "--agent-id" and i + 1 < len(sys.argv):
            config["agent_id"] = sys.argv[i + 1]
        elif arg == "--port" and i + 1 < len(sys.argv):
            config["event_listen_port"] = int(sys.argv[i + 1])
        elif arg == "--telemetry-interval" and i + 1 < len(sys.argv):
            config["telemetry_interval"] = int(sys.argv[i + 1])

    if not config["agent_id"]:
        log.error("AGENT_ID is required (env var, config file, or --agent-id)")
        sys.exit(1)

    return config


# ---------------------------------------------------------------------------
# Herald HTTP client
# ---------------------------------------------------------------------------

def herald_request(
    config: dict,
    method: str,
    path: str,
    body: dict | None = None,
    use_token: bool = False,
) -> dict | None:
    """Make an HTTP request to Herald. Returns parsed JSON or None."""
    url = f"{config['herald_url']}{path}"
    headers = {"Content-Type": "application/json"}

    if use_token and config.get("sidecar_token"):
        headers["Authorization"] = f"Bearer {config['sidecar_token']}"
    elif config.get("admin_key"):
        headers["X-Herald-Key"] = config["admin_key"]

    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()
        except Exception:
            pass
        log.error("Herald %s %s → %d: %s", method, path, e.code, body_text[:200])
        return None
    except URLError as e:
        log.error("Herald unreachable at %s: %s", url, e.reason)
        return None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_agent(config: dict) -> str | None:
    """Register this agent with Herald. Returns sidecar token."""
    allowed = (
        [a.strip() for a in config["allowed_actions"].split(",") if a.strip()]
        if isinstance(config["allowed_actions"], str)
        else config["allowed_actions"]
    )
    channels = (
        [c.strip() for c in config["channels"].split(",") if c.strip()]
        if isinstance(config["channels"], str)
        else config["channels"]
    )

    body = {
        "agent_id": config["agent_id"],
        "display_name": config["display_name"] or config["agent_id"],
        "tier": config["tier"],
        "allowed_actions": allowed,
        "channels": channels,
    }

    result = herald_request(config, "POST", "/api/v1/agents", body)
    if result and result.get("ok"):
        token = result["token"]
        log.info("Registered agent '%s' — token: %s...", config["agent_id"], token[:20])
        return token

    # Already registered? That's fine if we have a token
    if config.get("sidecar_token"):
        log.info("Agent may already be registered, using existing token")
        return config["sidecar_token"]

    log.error("Registration failed and no existing token available")
    return None


# ---------------------------------------------------------------------------
# Policy sync
# ---------------------------------------------------------------------------

def pull_policy(config: dict) -> dict | None:
    """Fetch current policy from Herald."""
    result = herald_request(
        config, "GET",
        f"/api/v1/agents/{config['agent_id']}/policy",
        use_token=True,
    )
    return result


def write_policy(config: dict, policy: dict) -> None:
    """Write policy to local file in the configured format."""
    path = Path(config["policy_path"])
    path.parent.mkdir(parents=True, exist_ok=True)

    fmt = config["policy_format"].lower()

    if fmt == "json":
        path.write_text(json.dumps(policy, indent=2), encoding="utf-8")
    elif fmt == "yaml" or fmt == "yml":
        try:
            import yaml
            path.write_text(yaml.dump(policy, default_flow_style=False), encoding="utf-8")
        except ImportError:
            # Fallback: write JSON even if yaml was requested
            json_path = path.with_suffix(".json")
            json_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")
            log.warning("PyYAML not installed, wrote JSON to %s", json_path)
            return
    elif fmt == "env":
        lines = []
        lines.append(f"HERALD_AGENT_ID={policy.get('agent_id', '')}")
        lines.append(f"HERALD_TIER={policy.get('tier', '')}")
        lines.append(f"HERALD_VERSION={policy.get('version', '')}")
        lines.append(f"HERALD_ALLOWED_ACTIONS={','.join(policy.get('allowed_actions', []))}")
        lines.append(f"HERALD_DENIED_ACTIONS={','.join(policy.get('denied_actions', []))}")
        lines.append(f"HERALD_CHANNELS={','.join(policy.get('channels', []))}")
        rl = policy.get("rate_limits", {})
        lines.append(f"HERALD_RATE_LIMIT_EVENTS={rl.get('events_per_minute', 60)}")
        lines.append(f"HERALD_RATE_LIMIT_API={rl.get('external_api_calls_per_minute', 10)}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif fmt == "toml":
        # Minimal TOML output without external deps
        lines = [
            f'agent_id = "{policy.get("agent_id", "")}"',
            f'tier = "{policy.get("tier", "")}"',
            f'version = {policy.get("version", 1)}',
            f'allowed_actions = {json.dumps(policy.get("allowed_actions", []))}',
            f'denied_actions = {json.dumps(policy.get("denied_actions", []))}',
            f'channels = {json.dumps(policy.get("channels", []))}',
            "",
            "[rate_limits]",
            f'events_per_minute = {policy.get("rate_limits", {}).get("events_per_minute", 60)}',
            f'external_api_calls_per_minute = {policy.get("rate_limits", {}).get("external_api_calls_per_minute", 10)}',
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        # Default to JSON
        path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    log.info("Policy written to %s (%s)", path, fmt)


def policy_sync_loop(config: dict, stop_event: threading.Event) -> None:
    """Periodically pull policy from Herald and write locally."""
    last_version = -1
    while not stop_event.is_set():
        policy = pull_policy(config)
        if policy and policy.get("version", -1) != last_version:
            write_policy(config, policy)
            last_version = policy.get("version", -1)
        stop_event.wait(config["heartbeat_interval"])


# ---------------------------------------------------------------------------
# Telemetry + heartbeat
# ---------------------------------------------------------------------------

def _parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _detect_remote_session(config: dict) -> bool:
    """Best-effort remote-session signal from environment hints."""
    hint = str(config.get("remote_session_hint", "")).strip().lower()
    if hint in {"1", "true", "yes", "remote"}:
        return True
    if hint in {"0", "false", "no", "local"}:
        return False

    for env_var in ("SSH_CLIENT", "SSH_CONNECTION", "SSH_TTY"):
        if os.getenv(env_var):
            return True
    return False


def _measure_herald_rtt_ms(config: dict) -> float | None:
    """Measure network RTT to Herald health endpoint."""
    url = f"{config['herald_url']}/health"
    req = Request(url, method="GET")
    start = perf_counter()
    try:
        with urlopen(req, timeout=5) as resp:
            resp.read(32)
        return (perf_counter() - start) * 1000.0
    except Exception:
        return None


def telemetry_loop(config: dict, stop_event: threading.Event) -> None:
    """Send telemetry signals for integrity checks."""
    interval = max(5, int(config["telemetry_interval"]))
    rtt_samples: deque[float] = deque(maxlen=20)

    while not stop_event.is_set():
        rtt_ms = _measure_herald_rtt_ms(config)
        if rtt_ms is not None:
            rtt_samples.append(rtt_ms)

        jitter_ms = None
        if len(rtt_samples) >= 2:
            jitter_ms = float(pstdev(rtt_samples))
        elif len(rtt_samples) == 1:
            jitter_ms = 0.0

        payload = {
            "agent_id": config["agent_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "probe_source": "sidecar",
            "telemetry_mode": config["telemetry_mode"],
            "network_rtt_ms": rtt_ms,
            "network_jitter_ms": jitter_ms,
            "is_remote_session": _detect_remote_session(config),
            "observed_provider": config["observed_provider"] or None,
            "observed_model": config["observed_model"] or None,
            "observed_region": config["observed_region"] or None,
            "sensor_hid_rtt_ms": _parse_optional_float(config.get("sensor_hid_rtt_ms")),
            "sensor_dwell_ms": _parse_optional_float(config.get("sensor_dwell_ms")),
            "sensor_os_jitter_ms": _parse_optional_float(config.get("sensor_os_jitter_ms")),
        }

        herald_request(config, "POST", "/api/v1/telemetry", payload, use_token=True)
        stop_event.wait(interval)


def heartbeat_loop(config: dict, stop_event: threading.Event) -> None:
    """Send periodic heartbeats to Herald."""
    while not stop_event.is_set():
        event = {
            "agent_id": config["agent_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "heartbeat",
            "target": "self",
            "result": "success",
        }
        herald_request(config, "POST", "/api/v1/events", event, use_token=True)
        stop_event.wait(config["heartbeat_interval"])


# ---------------------------------------------------------------------------
# Event listener (HTTP server on localhost)
# ---------------------------------------------------------------------------

class EventHandler(BaseHTTPRequestHandler):
    """Accepts events from the agent on localhost and forwards to Herald."""

    config: dict = {}

    def do_POST(self):
        if self.path != "/events":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_error(400, "Empty body")
            return

        body = self.rfile.read(content_length)
        try:
            event = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        # Ensure agent_id matches
        event["agent_id"] = self.config["agent_id"]

        # Forward to Herald
        result = herald_request(
            self.config, "POST", "/api/v1/events", event, use_token=True
        )

        if result:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_error(502, "Failed to forward event to Herald")

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "healthy",
                "agent_id": self.config.get("agent_id", ""),
            }).encode())
            return

        if self.path == "/policy":
            policy_path = Path(self.config["policy_path"])
            if policy_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(policy_path.read_bytes())
            else:
                self.send_error(404, "Policy not yet synced")
            return

        self.send_error(404)

    def log_message(self, format, *args):
        """Suppress default request logging — we use our own."""
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config = load_config()

    # --register mode: register and print token, then exit
    if "--register" in sys.argv:
        token = register_agent(config)
        if token:
            print(f"SIDECAR_TOKEN={token}")
            sys.exit(0)
        sys.exit(1)

    # Normal mode: register (if no token), then run
    if not config.get("sidecar_token"):
        token = register_agent(config)
        if not token:
            log.error("Cannot start without a valid token")
            sys.exit(1)
        config["sidecar_token"] = token

    # Initial policy pull
    policy = pull_policy(config)
    if policy:
        write_policy(config, policy)
    else:
        log.warning("Could not pull initial policy — will retry")

    # Shutdown coordination
    stop_event = threading.Event()

    def shutdown(signum, frame):
        log.info("Shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start background threads
    heartbeat_thread = threading.Thread(
        target=heartbeat_loop, args=(config, stop_event), daemon=True
    )
    heartbeat_thread.start()

    telemetry_thread = threading.Thread(
        target=telemetry_loop, args=(config, stop_event), daemon=True
    )
    telemetry_thread.start()

    policy_thread = threading.Thread(
        target=policy_sync_loop, args=(config, stop_event), daemon=True
    )
    policy_thread.start()

    # Start event listener
    EventHandler.config = config
    port = config["event_listen_port"]
    server = HTTPServer(("127.0.0.1", port), EventHandler)

    log.info("Sidecar ready for agent '%s'", config["agent_id"])
    log.info("  Events:    POST http://localhost:%d/events", port)
    log.info("  Health:    GET  http://localhost:%d/health", port)
    log.info("  Policy:    GET  http://localhost:%d/policy", port)
    log.info("  Herald:    %s", config["herald_url"])
    log.info("  Format:    %s → %s", config["policy_format"], config["policy_path"])
    log.info(
        "  Telemetry: POST /api/v1/telemetry every %ss (%s)",
        config["telemetry_interval"],
        config["telemetry_mode"],
    )

    try:
        while not stop_event.is_set():
            server.handle_request()
    except Exception:
        pass
    finally:
        server.server_close()
        log.info("Sidecar stopped")


if __name__ == "__main__":
    main()
