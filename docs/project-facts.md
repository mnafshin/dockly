# ProjectFacts schema

Structured detection model for **dockly** ([#5](https://github.com/mnafshin/dockly/issues/5)).
Implementation: `src/dockly/project_facts.py`. Related: [`project-detection.md`](project-detection.md).

## Principles

1. **Aggressive auto-detect** — prefer reading the project over asking the user.
2. **Config/CLI always wins** — `--build-tool`, `.dockly.toml`, and explicit flags override detected values (`override_fact`).
3. **Plugin surfaces seed known facts** — Maven/Gradle builder plugins imply `language=java` + build tool (`seed_implied_facts`); they still detect Java version, Spring vs plain, capabilities ([#8](https://github.com/mnafshin/dockly/issues/8)).
4. **`inspect` reports confidence + evidence** — each fact includes `confidence` and `evidence[]`.

## Schema

Each fact is:

| Field | Meaning |
|---|---|
| `value` | Detected or seeded value (`null` when unknown) |
| `confidence` | `high` \| `medium` \| `low` \| `unknown` |
| `source` | `detected` \| `cli` \| `config` \| `plugin_seed` |
| `evidence` | Human-readable reasons (paths, markers, flags) |

### Top-level facts

| Fact | Values | Notes |
|---|---|---|
| `language` | `java` | First-party v1 |
| `build_tool` | `maven` \| `gradle` | Marker detection; ambiguous ⇒ error unless CLI/seed |
| `java_version` | int or null | From POM properties / Gradle toolchain |
| `framework` | `spring-boot` \| `plain-java` | Spring markers vs none |
| `spring_boot_version` | string or null | Parent/plugin version when present |
| `project_kind` | `executable` \| `library` \| `multi-module` \| `unknown` | Heuristic |
| `packaging` | `jar` \| `war` \| `pom` \| `unknown` | Maven packaging; Gradle defaults to `jar` |
| `layout` | `single` \| `maven-reactor` \| `gradle-multi-project` | See project-detection |
| `capabilities.layered_jar` | bool | Spring Boot layertools path likely |
| `capabilities.actuator` | bool | `spring-boot-starter-actuator` in direct deps |
| `capabilities.spring_web` | bool | Web / WebFlux / WebSocket starters |

## Fixtures

| Fixture | Expect |
|---|---|
| `tests/fixtures/maven-only` | Spring Boot + Maven |
| `tests/fixtures/gradle-only` | Spring Boot + Gradle |
| `tests/fixtures/gradle-kts-only` | Spring Boot + Gradle Kotlin DSL |
| `tests/fixtures/plain-java-maven` | Plain Java + Maven (`framework=plain-java`) |
| `tests/fixtures/plain-java-gradle` | Plain Java + Gradle (`framework=plain-java`) |

## Ambiguity behavior

| Situation | Behavior |
|---|---|
| Both `pom.xml` and Gradle markers at root | **Fail** with message to pass `--build-tool` (CLI wins) |
| Spring Boot only in a submodule | `layout` multi-module; `spring_boot_modules` lists candidates; recommend `--project-root` |
| Java version missing | `java_version.value=null`, `confidence=unknown`; generator falls back to **17** |
| Spring markers without Boot version | `framework=spring-boot`, version null, medium confidence |
| Mixed evidence (Boot parent but no starters) | Still `spring-boot` if `spring-boot` string / application.yml present |
| Plugin seed + local markers disagree | Seed wins for seeded keys; remaining facts still detected |

```bash
dockly inspect --format json
# → payload.project_facts
```

## Precedence (callers)

1. CLI flag (e.g. `--build-tool`)
2. Config (`.dockly.toml` / legacy `.springdocker.toml`)
3. Plugin seed (`seed_implied_facts`)
4. Auto-detect
