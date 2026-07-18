# Contributing a language strategy

Short path for contributors — you do **not** need to read every ADR first.

**Product stance:** dockly maintains **Java + Spring Boot** first-party. Go, Python, Node, and
other languages are **community / later** ([ADR 0011](adr/0011-dockly-product-vision.md)).

## 10-minute map

| Doc | Why open it |
|---|---|
| [POSITIONING](POSITIONING.md) | What dockly is / is not |
| [project-facts.md](project-facts.md) | What you detect |
| [strategies.md](strategies.md) | Strategy contract + first-party table |
| [capabilities.md](capabilities.md) | How Java paths branch today |
| [examples/strategies/go/](examples/strategies/go/) | Unsupported Go stub (shape only) |

Core flow: **detect ProjectFacts → Policy → Strategy → generate → explain → verify**.

## Steps to add a strategy

1. **Facts** — Ensure detection (or a seed) can set `language` / `framework` for your stack.
2. **Strategy** — Implement `matches(facts, policy)` + `plan(facts, policy)` with a stable `id` and clear `rationale` (`src/dockly/strategy.py` pattern).
3. **Tests** — Fixtures for match/plan branches (see `tests/unit/test_strategy.py`).
4. **Docs** — One short section in `strategies.md`; do not claim first-party support unless maintainers agree.
5. **PR** — Keep language-specific Dockerfile recipes out of unrelated core helpers.

### Clear non-goals (v1)

- Go / Python / Node strategies are **not** first-party yet (Go stub is documentation only).
- Do not require polyglot CI matrices for experimental strategies.
- Java builder plugins stay **zero-Python** ([plugin-facts.md](plugin-facts.md), ADR 0010).

## Dev setup

See root [CONTRIBUTING.md](../CONTRIBUTING.md) for install, tests, and coverage.
