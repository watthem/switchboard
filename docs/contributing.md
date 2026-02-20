# Contributor Guide

Herald is MIT-licensed and accepts contributions. This guide covers the development workflow and standards.

---

## Getting Started

```bash
git clone https://github.com/watthem/herald.git
cd herald
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Development Workflow

1. Create a branch from `main`
2. Make your changes
3. Run tests: `pytest tests/ -v --tb=short`
4. Run lint: `ruff check herald/ tests/`
5. Run test quality guard: `python3 scripts/check_test_quality.py`
6. Open a pull request against `main`

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable. Docs, specs, tested code. PRs merged here. |
| `poc` | Product owner's engineering work via Claude Code. May be rough. |
| `dev` | Engineering branch (future, post-Gate 1). |

## Testing Standards

- All new endpoints need integration tests
- Business logic (integrity scoring, policy application) needs unit tests
- Tests must use the shared fixtures from `tests/conftest.py` for storage isolation
- The test quality guard enforces:
    - No tautological asserts (`assert True`, `assert x == x`)
    - Every test function has at least one assert
    - Status-code-only tests stay below 35% of total

## Code Style

- **Linter:** ruff (runs in CI)
- **Framework:** FastAPI + Pydantic v2
- **Storage:** File-backed JSON for POC (will move to a real database on DEV)
- **Sidecar:** Python 3.11+ stdlib only — no external dependencies

## What Goes Where

| Change | Location |
|--------|----------|
| Protocol endpoints | `herald/v1/routes.py` and `herald/v1/services.py` |
| Data models | `herald/v1/models.py` |
| Dashboard | `dashboard/index.html` |
| Sidecar | `sidecar/herald-sidecar.py` |
| Documentation | `docs/` (MkDocs, published to GitHub Pages) |
| Tests | `tests/` |

## Using AI Agents to Contribute

We expect contributors to use AI coding agents. See [AI Agent Rules](claude-contributor.md) for the repo-specific guardrails your agent should follow.
