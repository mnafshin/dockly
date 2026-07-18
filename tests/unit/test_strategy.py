from __future__ import annotations

import unittest
from pathlib import Path

from tests.test_support import add_src_to_path

add_src_to_path()

from dockly.dockerfile import DockerfileOptions
from dockly.project_facts import detect_project_facts
from dockly.strategy import (
    BUILTIN_STRATEGIES,
    Policy,
    StrategyRegistry,
    apply_strategy_plan,
    select_strategy,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class StrategyApiTests(unittest.TestCase):
    def test_registry_lists_three_first_party_strategies(self) -> None:
        ids = StrategyRegistry().list_ids()
        self.assertEqual(ids, ("spring-boot-layered", "spring-boot-jar", "plain-java"))
        self.assertEqual(len(BUILTIN_STRATEGIES), 3)

    def test_spring_maven_selects_layered(self) -> None:
        facts = detect_project_facts(FIXTURES / "maven-only")
        plan = select_strategy(facts)
        self.assertEqual(plan.strategy_id, "spring-boot-layered")
        self.assertTrue(plan.use_layered_jar)
        self.assertTrue(plan.spring_aware)
        self.assertIn("spring-boot-layertools", plan.optimizations)

    def test_spring_policy_forces_non_layered(self) -> None:
        facts = detect_project_facts(FIXTURES / "maven-only")
        plan = select_strategy(facts, Policy(force_layered_jar=False))
        self.assertEqual(plan.strategy_id, "spring-boot-jar")
        self.assertFalse(plan.use_layered_jar)
        self.assertTrue(plan.spring_aware)

    def test_plain_java_selects_jdk_path(self) -> None:
        facts = detect_project_facts(FIXTURES / "plain-java-maven")
        plan = select_strategy(facts)
        self.assertEqual(plan.strategy_id, "plain-java")
        self.assertFalse(plan.use_layered_jar)
        self.assertFalse(plan.spring_aware)
        self.assertIn("jdk-optimizations", plan.optimizations)
        self.assertNotIn("spring-boot-layertools", plan.optimizations)

    def test_plain_java_gradle_branch(self) -> None:
        facts = detect_project_facts(FIXTURES / "plain-java-gradle")
        plan = select_strategy(facts, Policy(use_jlink=False, enable_appcds=False))
        self.assertEqual(plan.strategy_id, "plain-java")
        self.assertFalse(plan.use_jlink)
        self.assertFalse(plan.enable_appcds)

    def test_apply_strategy_plan_updates_options(self) -> None:
        facts = detect_project_facts(FIXTURES / "plain-java-maven")
        plan = select_strategy(facts)
        options = DockerfileOptions(build_tool="maven", use_layered_jar=True)
        updated = apply_strategy_plan(options, plan)
        self.assertFalse(updated.use_layered_jar)


if __name__ == "__main__":
    unittest.main()
