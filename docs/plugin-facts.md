# Plugin-seeded facts (Maven / Gradle builders)

Java builder plugins **seed** known facts and **detect** the rest before strategy selection
([#8](https://github.com/mnafshin/dockly/issues/8)). CLI ProjectFacts helpers: [`project-facts.md`](project-facts.md).
ADR 0010 SSOT: plugins do **not** require `.dockly.toml`.

## Implied vs detected

| Fact | Maven plugin | Gradle plugin | Source |
|---|---|---|---|
| `language=java` | Implied | Implied | `plugin_seed` |
| `build_tool=maven` | Implied | — | `plugin_seed` |
| `build_tool=gradle` | — | Implied | `plugin_seed` |
| Java version | Detected / configured (`javaVersion`) | Detected / configured | detected or plugin config |
| Spring Boot vs plain Java | Detected from POM markers (CLI path) or assumed Boot-capable options on plugin defaults | Same for Gradle descriptors | detected |
| Layered JAR capability | Plugin `useLayeredJar` + Boot-oriented renderer | Extension `useLayeredJar` | plugin config (policy) |
| Modules / multi-module | Out of v1 plugin scope (point CLI at module) | Same | — |

The Python CLI can mirror seeds via:

```python
from dockly.project_facts import detect_project_facts, seed_implied_facts

facts = detect_project_facts(root, seeded=seed_implied_facts(build_tool="maven"))
```

## Decision note: shared rules vs duplication

| Concern | Choice |
|---|---|
| Dockerfile rendering rules | **Shared intent, two implementations** — pure-Java `DockerfileRenderer` (plugin) and Python `dockerfile.py` (CLI). Parity is intentional subset (ADR 0010); not a single shared binary. |
| ProjectFacts schema | **Python-canonical** for the CLI/Strategy API. Plugins encode the same *implications* in docs + Mojo defaults rather than depending on Python. |
| Strategy selection | **CLI-first** (`dockly.strategy`). Plugins apply an opinionated Boot/JDK option subset via `PluginDockerfileOptions` without loading the Python registry. |
| Why not one shared library? | Keeps the Java builder **zero-Python** (ADR 0010). Duplicating a thin option matrix is cheaper than a cross-language runtime. |

When adding a detection rule, update **both** `project_facts.py` (CLI) and plugin docs/defaults if the builder surface must behave the same.

## Tests / fixtures

| Case | Fixture / test |
|---|---|
| Spring Boot Maven | `tests/fixtures/maven-only` + `tests/unit/test_project_facts.py` (seed + Spring) |
| Plain Java Maven | `tests/fixtures/plain-java-maven` + seed tests |
| Plugin path without toml | `integrations/maven-plugin` generate/verify (no `.dockly.toml` read) |
