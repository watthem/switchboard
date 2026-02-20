# Local Development

Set up Herald for development with hot reload, testing, and linting.

---

## Setup

```bash
git clone https://github.com/watthem/herald.git
cd herald
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run with Hot Reload

```bash
uvicorn herald.app:app --port 59237 --reload
```

## Run Tests

```bash
pytest tests/ -v --tb=short
```

All tests use isolated temp directories for storage — no cleanup needed.

## Lint

```bash
ruff check herald/ tests/
```

## Test Quality Guard

A CI-integrated guard catches low-value test padding:

```bash
python3 scripts/check_test_quality.py
```

Fails on tautological asserts, zero-assert tests, and excessive status-code-only tests.

## Project Structure

```
herald/
├── herald/              # Python package
│   ├── app.py           # FastAPI app (~35 lines)
│   └── v1/              # Governance protocol endpoints
│       ├── models.py    # Pydantic models
│       ├── routes.py    # API routes (17 endpoints)
│       └── services.py  # Service layer (file-backed JSON)
├── sidecar/             # Reference sidecar (stdlib Python, zero deps)
├── dashboard/           # Fleet dashboard (single HTML file)
├── docs/                # Protocol spec, architecture, design tokens
├── examples/            # Integration examples
└── tests/               # pytest suite (78 tests)
```

## Storage

POC uses file-backed JSON in `data/v1/` (gitignored):

| File | Contents | Limit |
|------|----------|-------|
| `agents.json` | Agent registry | Unlimited |
| `events.json` | Audit log | 10,000 entries |
| `telemetry.json` | Telemetry stream | 10,000 entries |

## Port Map

| Port | Service |
|------|---------|
| 59237 | Herald API + Dashboard |
| 9100 | Sidecar event listener (per-agent, localhost only) |

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `HERALD_API_KEY` | Admin API key. Unset = dev mode (no auth). | No |
