# dockly positioning

**dockly** is a policy-driven Dockerfile generator: detect project facts → apply policy/profile →
generate a reviewable Dockerfile → explain → verify. Product vision: [ADR 0011](adr/0011-dockly-product-vision.md).

It targets the middle ground between black-box image builders and fully hand-written Dockerfiles:

- You get a generated Dockerfile with strong defaults.
- You keep direct ownership of the container definition.
- You can explain (advisory review) and verify (CI gates) the output.

### Core + strategies

| Layer | Responsibility |
|---|---|
| **Core** | Detect → policy/profile → generate → explain → verify |
| **Strategies** | Language/framework Dockerfile optimizations from detected facts + policy |

**First-party in v1:** Java and Spring Boot (including plain Java JDK paths). **Not first-party in v1:**
Go, Python, and other language strategies — community/later via the Strategy API
([#6](https://github.com/mnafshin/dockly/issues/6)). See [ADR 0011 non-goals](adr/0011-dockly-product-vision.md#non-goals-v1).

`explain` uses static text heuristics — useful for documentation and PR review, not a security or correctness audit. `verify` runs tool-backed and config checks with pass/fail semantics; use it to block merges. See [cli/README.md](../cli/README.md#explain-command).

This document separates **what the CLI ships and CI validates** from **what the benchmark sample demonstrates** and **what remains roadmap**. Install surfaces use **dockly** ([#3](https://github.com/mnafshin/dockly/issues/3)); legacy `.dockly.toml` / `SPRINGDOCKER_*` remain accepted during the deprecation window ([#9](https://github.com/mnafshin/dockly/issues/9)).

## Target audience

Resolved in [ADR 0008](adr/0008-target-audience.md) (audience decision from the dockly era; product name is now **dockly** per [ADR 0011](adr/0011-dockly-product-vision.md)).

**Primary: production teams** adopting Java / Spring Boot containerization with a Dockerfile they own, review in PRs, and verify in CI. Install from PyPI; run against your service; use Java 17+ and your Spring Boot version via config.

**Secondary: conference and evidence storytelling.** Presentations, benchmark scenarios, and the reference sample (`Spring Boot 4`, `Java 25`) live in this repository to support reproducible talks and tuning evidence. They are optional — not required for production rollout and not claims about every user's stack. Ownership, update cadence, and publish policy: [`docs/presentation/README.md`](presentation/README.md).

**Not primary: lab-only research tooling.** Stress-testing happens in-repo; the shipped CLI is general-purpose for real projects.

### Java 25 / Spring Boot 4 in the reference sample (not CLI default)

The benchmark sample uses bleeding-edge versions to exercise generator output and publish evidence. That is intentional for the **secondary** audience. The **CLI** falls back to **Java 17** when the project version is undetected. Production users configure `java_version` and profiles for their own LTS or current JDK — see [adopt.md](adopt.md). The sample version choice is a **feature for evidence depth**, not a requirement for adoption.

## Distribution

**Two install surfaces:**

| Path | Use when |
|---|---|
| `pip install dockly` / `pipx` / `uv tool` | Full toolkit — Dockerfile, explain, verify, benchmarks; `.dockly.toml` SSOT ([ADR 0005](adr/0005-config-first-dockerfile-generation.md)) |
| Maven plugin `io.github.mnafshin:dockly-maven-plugin` | Java-only builder — generate/verify from `pom.xml`; no Python ([ADR 0010](adr/0010-pom-gradle-ssot-java-builder.md)) |
| Clone + `python scripts/checkout_sample.py` | Reproduce benchmark scenarios, reference CSVs, presentation numbers ([`java-spring-docker-sample`](https://github.com/mnafshin/java-spring-docker-sample)) |
| Clone + editable install | CLI development ([CONTRIBUTING.md](../CONTRIBUTING.md)) |

**PyPI-first** remains the distribution model for the CLI ([ADR 0006](adr/0006-pypi-first-distribution.md)). The Maven plugin is a separate artifact (local `mvn install` today; Maven Central tracked in [#145](https://github.com/mnafshin/dockly/issues/145)).

The reference sample is a separate repository, pinned from this one. See [ADR 0009](adr/0009-external-sample-repository.md).

## Product scope

dockly is a **policy-driven Dockerfile generator** with a language-agnostic core. **Java + Spring Boot**
are first-party strategies; other languages are community/later ([ADR 0011](adr/0011-dockly-product-vision.md)).

| In scope today | Out of scope today (v1 non-goals) |
|---|---|
| Project detection, config, Dockerfile generation | First-party Go / Python / Node strategies |
| `explain` — advisory static analysis for human review | Using `explain` as a security or correctness CI gate |
| `verify` — pass/fail checks for CI (config SSOT, optional hadolint/trivy/…) | Guaranteed native-image production workflow |
| Optional benchmark asset generation, run, and analyze | Universal JVM tuning prescriptions for every workload |
| Plugin hooks for recipes, mutators, and verifiers | Full compatibility matrix across all Spring Boot versions |
| Strategy API for contributors ([#6](https://github.com/mnafshin/dockly/issues/6)) | Replacing your CI platform or registry |

The CLI supports **Java 17+** on Maven/Gradle projects (Spring Boot and plain Java paths as strategies mature). When `java_version` is omitted, dockly prefers the **detected** project Java, then falls back to **17**. The **reference sample** ([`java-spring-docker-sample`](https://github.com/mnafshin/java-spring-docker-sample)) stays on Spring Boot 4 / Java 25 to drive benchmark evidence and presentation numbers — that is not a claim that every user must run Java 25.

## Shipped guarantees (CI-evidenced)

These behaviors are enforced by [`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

| Area | What CI proves |
|---|---|
| **CLI quality** | `ruff` lint, `mypy` on `src/`, pytest suites (`unit`, `integration`, `e2e`, `benchmark`) on Ubuntu/macOS/Windows and Python 3.10–3.12 |
| **Package coverage** | ≥80% line coverage on the entire `dockly` package (same gate as local `pytest`; see `pyproject.toml`) |
| **Dockerfile generation** | Snapshot and e2e tests on `tests/fixtures/{maven-only,gradle-only}` — output shape, flags, and explain/verify wiring |
| **Benchmark generator** | `benchmark-hygiene` checks out the pinned sample, runs `benchmark generate`, and asserts generated assets stay gitignored in the sample repo |
| **Benchmark analyzer** | `benchmark-regression` verifies sample `03-base-image-choice/results/baseline.json` matches analyze output for the paired `raw.csv`, then runs the 20% regression comparator |
| **Docker smoke build** | `docker-smoke` generates a Dockerfile for the pinned sample checkout, runs `docker build`, and probes `/actuator/health/readiness` on port 8081 |
| **Supply chain (repo)** | SPDX SBOM artifact, **blocking** CRITICAL Trivy filesystem scan, and `digest-pins` job verifying registry manifests for `digest_pins.py` |

What CI **does not** prove today:

- Full benchmark suite execution against real Docker on every push.
- `dockly verify` with hadolint, trivy, dive, or cosign installed — verify tests mock or skip external tools.
- Performance numbers in presentations or docs — those come from local/reference runs on the sample app.

Public docs and talks should treat benchmark tables as **sample evidence**, not fleet-wide guarantees, unless you reproduce them on your project.

## Optional evidence subsystem

Benchmarks are an **opt-in extra** (`pip install dockly[benchmark]`):

1. `benchmark generate` — writes scenario Dockerfiles locally (gitignored under the sample tree).
2. `benchmark run` — requires Docker on the host; skipped for native scaffold scenarios by default.
3. `benchmark analyze` / `compare` — summarize `raw.csv`; one pinned baseline is gated in CI.

Use benchmarks to **inform** Dockerfile and JVM decisions on your service. They do not replace policy choices (non-root, digest pins, SBOM) or service-specific profiling.

See [`benchmarks.md`](benchmarks.md) and the sample’s [`benchmarks/README.md`](https://github.com/mnafshin/java-spring-docker-sample/blob/main/benchmarks/README.md) for artifact policy.

## Sample project strategy (two trees)

CLI onboarding/regression stays in this repository; evidence depth lives in an external sample:

| Path | Audience | Validated in CI |
|---|---|---|
| `tests/fixtures/{maven-only,gradle-only}/` | Humans learning the CLI and automated regression | unit, integration, e2e, benchmark tests |
| [`java-spring-docker-sample`](https://github.com/mnafshin/java-spring-docker-sample) → `samples/java-spring-docker/` | Benchmark harness and reference evidence | generator hygiene + analyzer regression on pinned CSV + `docker-smoke` build/readiness |

Fixtures are minimal (CLI/output shape only). Full Docker builds and presentation numbers use the external sample (checked out under `samples/`). Do not copy the full benchmark tree into every consumer repo.

Resolved in [#95](https://github.com/mnafshin/dockly/issues/95) / ADR 0004; externalization in [ADR 0009](adr/0009-external-sample-repository.md).

## Reference stack vs compatibility

| Layer | CLI / production path | Reference sample (evidence) |
|---|---|---|
| Spring Boot | Maven/Gradle projects with Spring Boot markers | 4.0.1 sample app |
| Java | Floor **17**; init/undetected fallback **17**; JEP 483 AOT **24+** | **25** in sample `.dockly.toml` (includes scenario 02) |
| Python CLI | Requires Python ≥3.10 | 3.12 in CI |

Feature matrix and support ranges: [jvm.md](jvm.md).

Production teams set `java_version` in `.dockly.toml` for their service. The reference sample stays on current JDK/Spring Boot for benchmark and presentation refresh — see [ADR 0008](adr/0008-target-audience.md).

## Why not Jib?

Jib is excellent when you want fast Java image builds without writing Dockerfiles.  
The tradeoff is reduced direct control over the final Dockerfile-level shape.

Choose Jib when:
- your team wants minimal container-layer customization
- Dockerfile ownership is not required

Choose dockly when:
- your team wants a real Dockerfile artifact in-repo
- you need explicit, reviewable container decisions

## Why not Buildpacks / Paketo / `spring-boot:build-image`?

Buildpacks are great for zero-configuration builds and ecosystem integration.  
The tradeoff is an opinionated build pipeline that can feel opaque when debugging image-level behavior.

Choose Buildpacks when:
- platform defaults are enough
- your team is comfortable with buildpack internals and lifecycle behavior

Choose dockly when:
- you need explicit Dockerfile ownership
- you want explainable, reviewable Dockerfile output as a first-class artifact

## Why not hand-written Dockerfiles?

Hand-written Dockerfiles maximize control and flexibility, but they are easy to drift and costly to keep aligned with evolving best practices.

Choose hand-written Dockerfiles when:
- your image has highly custom constraints that generators cannot model

Choose dockly when:
- you want a maintainable baseline generated from repeatable conventions
- you still want manual control after generation

## Summary

dockly is for teams that want:

1. a Dockerfile they can own and edit
2. opinionated defaults for Java / Spring Boot containerization (first-party strategies)
3. explain-and-verify workflows around the generated output
4. optional, reproducible benchmark evidence — not a black-box image builder
5. a clear extension path for other languages via strategies — without first-party polyglot maintenance in v1

## Related issues

- [#1](https://github.com/mnafshin/dockly/issues/1) — this product vision (ADR 0011)
- [#3](https://github.com/mnafshin/dockly/issues/3) — surface rebrand (CLI, PyPI, config, Action, env)
- [#6](https://github.com/mnafshin/dockly/issues/6) — Strategy API
- [#9](https://github.com/mnafshin/dockly/issues/9) — optional dockly compatibility shims
- [#10](https://github.com/mnafshin/dockly/issues/10) — contributor guide + strategy stubs
