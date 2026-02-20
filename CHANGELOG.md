# Changelog

## 2026.02.19-POC — Initial Release

### Added
- Herald v1 governance API (FastAPI)
- Agent registration, policy management, event ingestion, telemetry
- Integrity scoring (100-point system with policy-aware penalty checks)
- Policy presets (standard, strict, relaxed) with fleet-wide application
- File-backed JSON storage (POC)
- Reference sidecar (zero-dep Python 3.11+)
- Fleet dashboard (single HTML file, WCAG AA)
- Examples: Ruby agent, fleet registration script, Claude Code hook
- Protocol specification (docs/PROTOCOL.md)
- CI: pytest + ruff on every PR (Python 3.11 + 3.12)
- Release automation: tagged releases create GitHub Releases with distributions
