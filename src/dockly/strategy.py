"""Strategy API: ProjectFacts + Policy → Dockerfile optimization plan.

First-party strategies (Java / Spring). Community languages register via
``dockly.strategies`` entry points later; see docs/strategies.md.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from .dockerfile import DockerfileOptions
from .project_facts import ProjectFacts


@dataclass(frozen=True)
class Policy:
    """Policy/profile constraints. ``None`` means “let the strategy decide”."""

    force_layered_jar: bool | None = None
    use_jlink: bool | None = None
    enable_appcds: bool | None = None
    runtime_image: str | None = None

    @classmethod
    def from_dockerfile_config(
        cls,
        *,
        use_layered_jar: bool | None = None,
        use_jlink: bool | None = None,
        enable_appcds: bool | None = None,
        runtime_image: str | None = None,
        force_layered_jar: bool | None = None,
    ) -> Policy:
        # When callers pass an explicit layered bool from CLI/config, treat as force.
        layered_force = force_layered_jar
        if layered_force is None and use_layered_jar is not None:
            layered_force = use_layered_jar
        return cls(
            force_layered_jar=layered_force,
            use_jlink=use_jlink,
            enable_appcds=enable_appcds,
            runtime_image=runtime_image,
        )


@dataclass(frozen=True)
class StrategyPlan:
    strategy_id: str
    name: str
    use_layered_jar: bool
    spring_aware: bool
    use_jlink: bool
    enable_appcds: bool
    optimizations: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "use_layered_jar": self.use_layered_jar,
            "spring_aware": self.spring_aware,
            "use_jlink": self.use_jlink,
            "enable_appcds": self.enable_appcds,
            "optimizations": list(self.optimizations),
            "rationale": self.rationale,
        }


class Strategy(Protocol):
    id: str
    name: str

    def matches(self, facts: ProjectFacts, policy: Policy) -> bool: ...

    def plan(self, facts: ProjectFacts, policy: Policy) -> StrategyPlan: ...


def _bool_policy(policy_value: bool | None, default: bool) -> bool:
    return default if policy_value is None else policy_value


class SpringBootLayeredStrategy:
    id = "spring-boot-layered"
    name = "Spring Boot layered JAR"

    def matches(self, facts: ProjectFacts, policy: Policy) -> bool:
        if facts.framework.value != "spring-boot":
            return False
        if policy.force_layered_jar is False:
            return False
        if policy.force_layered_jar is True:
            return True
        return bool(facts.capabilities.layered_jar.value)

    def plan(self, facts: ProjectFacts, policy: Policy) -> StrategyPlan:
        use_jlink = _bool_policy(policy.use_jlink, True)
        enable_appcds = _bool_policy(policy.enable_appcds, True)
        opts = [
            "spring-boot-layertools",
            "multi-stage-build",
        ]
        if use_jlink:
            opts.append("jlink-custom-jre")
        if enable_appcds:
            opts.append("appcds")
        return StrategyPlan(
            strategy_id=self.id,
            name=self.name,
            use_layered_jar=True,
            spring_aware=True,
            use_jlink=use_jlink,
            enable_appcds=enable_appcds,
            optimizations=tuple(opts),
            rationale=(
                "Spring Boot project with layered JAR capability "
                f"(layered_jar confidence={facts.capabilities.layered_jar.confidence})"
            ),
        )


class SpringBootNonLayeredStrategy:
    id = "spring-boot-jar"
    name = "Spring Boot executable JAR"

    def matches(self, facts: ProjectFacts, policy: Policy) -> bool:
        if facts.framework.value != "spring-boot":
            return False
        if policy.force_layered_jar is True:
            return False
        if policy.force_layered_jar is False:
            return True
        return not bool(facts.capabilities.layered_jar.value)

    def plan(self, facts: ProjectFacts, policy: Policy) -> StrategyPlan:
        use_jlink = _bool_policy(policy.use_jlink, True)
        enable_appcds = _bool_policy(policy.enable_appcds, True)
        opts = [
            "spring-boot-executable-jar",
            "multi-stage-build",
            "java-optimizations",
        ]
        if use_jlink:
            opts.append("jlink-custom-jre")
        if enable_appcds:
            opts.append("appcds")
        return StrategyPlan(
            strategy_id=self.id,
            name=self.name,
            use_layered_jar=False,
            spring_aware=True,
            use_jlink=use_jlink,
            enable_appcds=enable_appcds,
            optimizations=tuple(opts),
            rationale=(
                "Spring Boot project without layered JAR path "
                "(policy or capability); keep Spring-aware executable JAR"
            ),
        )


class PlainJavaStrategy:
    id = "plain-java"
    name = "Plain Java JDK"

    def matches(self, facts: ProjectFacts, policy: Policy) -> bool:
        return facts.framework.value == "plain-java"

    def plan(self, facts: ProjectFacts, policy: Policy) -> StrategyPlan:
        use_jlink = _bool_policy(policy.use_jlink, True)
        enable_appcds = _bool_policy(policy.enable_appcds, True)
        opts = ["multi-stage-build", "jdk-optimizations"]
        if use_jlink:
            opts.append("jlink-custom-jre")
        if enable_appcds:
            opts.append("appcds")
        return StrategyPlan(
            strategy_id=self.id,
            name=self.name,
            use_layered_jar=False,
            spring_aware=False,
            use_jlink=use_jlink,
            enable_appcds=enable_appcds,
            optimizations=tuple(opts),
            rationale="Plain Java project — no Spring Boot assumptions (no layertools)",
        )


BUILTIN_STRATEGIES: tuple[Strategy, ...] = (
    SpringBootLayeredStrategy(),
    SpringBootNonLayeredStrategy(),
    PlainJavaStrategy(),
)


class StrategyRegistry:
    def __init__(self, strategies: tuple[Strategy, ...] | None = None) -> None:
        self._strategies = strategies if strategies is not None else BUILTIN_STRATEGIES

    def select(self, facts: ProjectFacts, policy: Policy | None = None) -> StrategyPlan:
        pol = policy or Policy()
        for strategy in self._strategies:
            if strategy.matches(facts, pol):
                return strategy.plan(facts, pol)
        # Fallback: treat unknown framework as plain Java JDK path
        return PlainJavaStrategy().plan(facts, pol)

    def list_ids(self) -> tuple[str, ...]:
        return tuple(s.id for s in self._strategies)


_DEFAULT_REGISTRY = StrategyRegistry()


def select_strategy(facts: ProjectFacts, policy: Policy | None = None) -> StrategyPlan:
    """Select a Dockerfile optimization plan from facts + policy."""
    return _DEFAULT_REGISTRY.select(facts, policy)


def apply_strategy_plan(options: DockerfileOptions, plan: StrategyPlan) -> DockerfileOptions:
    """Merge strategy decisions into DockerfileOptions (strategy fills gaps already decided by policy)."""
    return replace(
        options,
        use_layered_jar=plan.use_layered_jar,
        use_jlink=plan.use_jlink,
        enable_appcds=plan.enable_appcds,
    )
