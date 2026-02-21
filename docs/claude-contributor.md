# AI Agent Rules (CLAUDE.md)

Rules for AI coding agents contributing to Switchboard. If you use Claude Code, Cursor, Copilot, or any AI assistant to write code for this repo, these are the guardrails.

---

## What Switchboard Is

Switchboard is a governance protocol for AI agent fleets. It manages the boundary around agents — not the agents themselves. Runtime-agnostic: any language, any framework.

## Project Structure

```
switchboard/
├── switchboard/              # Python package
│   ├── app.py           # FastAPI app (~35 lines)
│   └── v1/              # Governance protocol endpoints
│       ├── models.py    # Pydantic models
│       ├── routes.py    # API routes (17 endpoints)
│       └── services.py  # Service layer (file-backed JSON)
├── sidecar/             # Reference sidecar (stdlib Python, zero deps)
├── dashboard/           # Fleet dashboard (single HTML file)
├── docs/                # Documentation (MkDocs → GitHub Pages)
├── examples/            # Integration examples
└── tests/               # pytest suite
```

## Commands

```bash
# Development
pip install -e ".[dev]"
uvicorn switchboard.app:app --port 59237 --reload

# Testing
pytest tests/ -v --tb=short
ruff check switchboard/ tests/
python3 scripts/check_test_quality.py

# Documentation
pip install mkdocs-material
mkdocs serve  # preview at localhost:8000
mkdocs build  # build static site
```

## Rules for AI Agents

### Do

- Run `pytest` and `ruff check` before suggesting your changes are complete
- Use the shared test fixtures from `tests/conftest.py` (isolated storage, admin headers, registered agents)
- Keep the sidecar stdlib-only — no external dependencies
- Match the existing code style (the codebase is small, read it first)

### Don't

- Don't add new dependencies without discussing in the PR
- Don't modify `docs/shared.css` without understanding the design system
- Don't skip the test quality guard — it runs in CI
- Don't add framework abstractions — Switchboard is intentionally simple
- Don't "improve" code you weren't asked to change

## Port Map

| Port | Service |
|------|---------|
| 59237 | Switchboard API + Dashboard |
| 9100 | Sidecar event listener (per-agent, localhost only) |

## Storage

File-backed JSON in `data/v1/` (gitignored). Tests use `tmp_path` — never touch real storage.

## Architecture Notes

- v1 endpoints have no external deps beyond FastAPI/Pydantic
- Sidecar is stdlib-only Python 3.11+
- Dashboard is a single HTML file with inline JS
- Design tokens in `docs/shared.css` (dark theme, WCAG AA)
