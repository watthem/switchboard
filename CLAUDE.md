# CLAUDE.md — Herald

## What This Is

Herald is a governance protocol for AI agent fleets. It manages the boundary around agents — not the agents themselves. Runtime-agnostic: any language, any framework.

## Project Structure

```
herald/
├── herald/              # Python package
│   ├── __init__.py      # Version
│   ├── app.py           # FastAPI app (~35 lines)
│   └── v1/              # Governance protocol endpoints
│       ├── models.py    # Pydantic models
│       ├── routes.py    # API routes
│       └── services.py  # Service layer (file-backed JSON storage)
├── sidecar/             # Reference sidecar (stdlib Python, zero deps)
├── dashboard/           # Fleet dashboard (single HTML file + shared.css)
├── docs/                # Protocol spec, architecture, design tokens
└── examples/            # Integration examples
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn herald.app:app --port 59237 --reload
```

## Key Commands

```bash
# Start Herald
uvicorn herald.app:app --port 59237

# Register example agents
python examples/register-fleet.py

# Run sidecar for an agent
HERALD_URL=http://localhost:59237 AGENT_ID=my-agent python sidecar/herald-sidecar.py

# Health check
curl http://localhost:59237/health

# Dashboard
open http://localhost:59237/dashboard
```

## Port Map

| Port | Service |
|------|---------|
| 59237 | Herald API + Dashboard |
| 9100 | Sidecar event listener (per-agent, localhost only) |

## Storage

POC uses file-backed JSON in `data/v1/` (gitignored). Files:
- `data/v1/agents.json` — agent registry
- `data/v1/events.json` — event log (max 10k)
- `data/v1/telemetry.json` — telemetry stream (max 10k)

## Architecture Notes

- v1 endpoints have no external deps beyond FastAPI/Pydantic
- Sidecar is stdlib-only Python 3.11+
- Dashboard is a single HTML file with inline JS, served by Herald
- Design tokens in `docs/shared.css` (dark theme, WCAG AA)
