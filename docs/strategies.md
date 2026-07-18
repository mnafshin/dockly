# Strategy API

Strategies turn **ProjectFacts** + **Policy** into a Dockerfile optimization plan.
Core still owns detect → policy → generate → explain → verify ([ADR 0011](adr/0011-dockly-product-vision.md)).

Implementation: `src/dockly/strategy.py`. Facts: [`project-facts.md`](project-facts.md).

## Contract

```text
ProjectFacts + Policy → StrategyPlan
```

| Type | Role |
|---|---|
| `ProjectFacts` | What the project is (language, Spring vs plain, capabilities) |
| `Policy` | User preferences (`force_layered_jar`, jlink, AppCDS, …); `None` = strategy default |
| `StrategyPlan` | Chosen path + rationale + optimization flags |
| `Strategy` | `matches(facts, policy)` + `plan(facts, policy)` |

```python
from dockly.project_facts import detect_project_facts
from dockly.strategy import Policy, select_strategy

facts = detect_project_facts(project_root)
plan = select_strategy(facts, Policy(force_layered_jar=True))
print(plan.strategy_id, plan.rationale)
```

`dockly inspect --format json` includes a `strategy` object.

## First-party strategies (v1)

| ID | When | Behavior |
|---|---|---|
| `spring-boot-layered` | Spring Boot + layered capable (or policy forces layered on) | Layertools path + Java optimizations |
| `spring-boot-jar` | Spring Boot + layered off / not capable | Executable JAR + Java optimizations (Spring-aware) |
| `plain-java` | `framework=plain-java` | JDK path (jlink / multi-stage / AppCDS per policy) — **no** Boot / layertools assumptions |

Registry order: layered → non-layered Spring → plain Java. Unknown frameworks fall back to `plain-java`.

## Policy / CLI precedence

1. Explicit policy (`force_layered_jar`, config/CLI flags)
2. Strategy defaults from facts
3. Built-in Dockerfile option defaults

Generate applies the selected plan so plain Java never enables Spring layertools.

## Adding a language strategy (contributors)

dockly maintains **Java + Spring** first-party. Other languages are community/later.

1. Detect enough `ProjectFacts` for your language (or seed via a plugin).
2. Implement a `Strategy` with a stable `id` and clear `rationale`.
3. Register it (today: extend `StrategyRegistry` / PR into first-party only for Java; external entry points are planned).
4. Add fixtures + tests for match/plan branches.
5. Do **not** put language-specific Dockerfile recipes in core helpers.

### Unsupported Go stub

See [`docs/examples/strategies/go/`](examples/strategies/go/) for a **non-shipping** sketch of a Go strategy shape. It is documentation only — Go is not first-party in v1.
