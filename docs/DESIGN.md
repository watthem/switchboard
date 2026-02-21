# DESIGN.md — Switchboard Design System

> **Diataxis category:** Reference
> **Source:** `docs/shared.css`

A portable, token-based dark-theme design system. No build tools required — link one CSS file and go.

---

## Quick Start

```html
<link rel="stylesheet" href="/docs/shared.css">
<body>
  <div class="container">Your content here</div>
</body>
```

Dark theme, centered layout, system font stack — all from one file.

---

## Design Tokens

### Color Palette

| Token | Value | Use |
|-------|-------|-----|
| `--bg-void` | `#0a0a0c` | Page background |
| `--bg-obsidian` | `#121215` | Card backgrounds |
| `--bg-charcoal` | `#1a1a1f` | Elevated surfaces |
| `--bg-steel` | `#2a2a32` | Borders |
| `--text-primary` | `#f5f5f7` | Body text (15:1 contrast) |
| `--text-secondary` | `#a8a8b0` | Labels (7:1 contrast) |
| `--accent` | `#d4a24e` | Gold — status/ok |
| `--accent-blue` | `#6b8cba` | Links, active states |
| `--status-ok` | `#4ec9a0` | Healthy/normal |
| `--status-warn` | `#c48a3a` | Elevated/warning |
| `--status-error` | `#b0614e` | Degraded/error |

### Typography

- **UI:** Outfit (sans-serif)
- **Metrics/Code:** Space Mono (monospace)

### Governance Tokens

Tier and integrity colors for the fleet dashboard:

| Token | Maps To |
|-------|---------|
| `--tier-l0` | `--accent-blue` |
| `--tier-l1` | `--status-ok` |
| `--tier-l2` | `--status-warn` |
| `--tier-l3` | `--status-error` |
| `--integrity-normal` | `--status-ok` |
| `--integrity-elevated` | `--status-warn` |
| `--integrity-degraded` | `--status-error` |

---

## Components

### Nav

Sticky top navigation with brand, links, and status indicator.

```html
<nav class="nav">
  <div class="nav__inner">
    <a href="/dashboard" class="nav__brand">switchboard <span>/ fleet</span></a>
    <a href="/dashboard" class="active">Dashboard</a>
    <div class="nav__status">
      <div class="nav__dot"></div>
      <span>3 agents</span>
    </div>
  </div>
</nav>
```

### Agent Cards

Fleet grid with tier color, status dot, integrity badge.

```html
<div class="fleet-grid">
  <div class="agent-card" style="--card-tier-color: #00ff88">
    <div class="agent-card__head">
      <div class="agent-card__dot agent-card__dot--online"></div>
      <div class="agent-card__name">My Agent</div>
      <div class="agent-card__tier">L1 Assistant</div>
    </div>
    <div class="agent-card__meta">...</div>
  </div>
</div>
```

### Stat Row, Detail Panel, Tier Selector, Permission Grid

See `dashboard/index.html` for live usage of all components.

---

## Accessibility

- Skip links (`<a class="skip-link">`)
- Screen reader utility (`.sr-only`)
- Focus-visible rings on interactive elements
- `prefers-reduced-motion` respected
- ARIA landmarks, labels, and live regions
- WCAG AA contrast ratios (primary 15:1, secondary 7:1)

---

## Philosophy

"Refined, not neon." Desaturated teal, gold, and blue. No glow effects. Instrument-panel aesthetic — professional and readable.
