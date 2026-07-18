# Typing roadmap

Resolved in [#90](https://github.com/mnafshin/dockly/issues/90).

`dockly` uses **gradual typing**: mypy runs on `src/` in CI with pragmatic defaults today, and stricter checks roll out module-by-module so the type-check job stays green.

## Current baseline (all of `src/`)

Configured in `[tool.mypy]` in `pyproject.toml`:

| Setting | Value | Rationale |
|---|---|---|
| `files` | `["src"]` | Package code only; tests stay pytest-first for now |
| `ignore_missing_imports` | `true` | Third-party stubs are incomplete; revisit per dependency |
| `no_implicit_optional` | `true` | Catch `None` default mistakes early |
| `warn_unused_ignores` | `true` | Remove stale `# type: ignore` comments |

CI job: `.github/workflows/ci.yml` → `mypy` (reads `pyproject.toml`).

Local check: `mypy src` or `mypy` from repo root.

## Phase 1 — strict core modules (shipped)

These modules use **per-module overrides** with `disallow_untyped_defs` and `warn_return_any`:

- `dockly.errors`
- `dockly.digest_pins`
- `dockly.dockerfile_explain`
- `dockly.compare`
- `dockly.config_audit`
- `dockly.runtime_images`
- `dockly.services.verify_service`

When a module is listed under `[[tool.mypy.overrides]]`, new functions in that file must have complete annotations and avoid untyped `Any` returns.

## Phase 2 — services and small helpers (shipped)

These modules use the same **per-module overrides** as Phase 1 (`disallow_untyped_defs`, `warn_return_any`):

- `dockly.services.project_service`
- `dockly.services.dockerfile_service`
- `dockly.services.benchmark_service`
- `dockly.regression`

## Phase 3 — CLI surface and config (next)

- `dockly.cli`
- `dockly.commands`
- `dockly.config`
- `dockly.configure_wizard`
- `dockly.dockerfile_profiles`

These files carry argparse wiring and large config dataclasses. Tighten return types (e.g. `DockerfileGenerateConfig` instead of `object`) before enabling strict mode globally in this layer.

## Phase 4 — generation and plugins

- `dockly.dockerfile` (large template module; IDE Dockerfile injection can confuse editors — see [ide/intellij.md](ide/intellij.md))
- `dockly.plugins`
- `dockly.benchmarks.*`

Benchmark runner subprocess code may keep targeted ignores longer.

## Phase 5 — tests (optional, non-blocking)

Incremental options (not in CI yet):

```bash
mypy tests/unit/test_config.py --disallow-untyped-defs
```

Prefer typing **test helpers** and **fixtures** first. Full test strictness is lower priority than production `src/`.

## Phase 6 — dependency stubs

Reduce `ignore_missing_imports` per package when types are available:

1. Add or pin stubs in `[project.optional-dependencies] dev`
2. Add `[[tool.mypy.overrides]]` with `ignore_missing_imports = false` for that import only
3. Fix fallout in dependent modules

## How to extend strict coverage

1. Run strict probe on one module:

   ```bash
   mypy src/dockly/errors.py --disallow-untyped-defs --warn-return-any
   ```

2. Fix reported issues in that module (and any imports it pulls in under the same command).

3. Append the module path to `[[tool.mypy.overrides]].module` in `pyproject.toml`.

4. Run `mypy src` and `pytest` before pushing.

Do **not** flip global `strict = true` until Phases 2–4 are largely complete — that creates noisy churn across unrelated files.

## Related tooling

- **Pyright** (`[tool.pyright]` in `pyproject.toml`) includes `src` and `tests` for IDE feedback; it is not gated in CI today.
- **Ruff** does not replace mypy for static typing — both run in CI.
