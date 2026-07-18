from __future__ import annotations

import unittest
from pathlib import Path

from tests.test_support import add_src_to_path

add_src_to_path()

from dockly.project_facts import detect_project_facts, override_fact, seed_implied_facts

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class ProjectFactsTests(unittest.TestCase):
    def test_spring_maven_fixture(self) -> None:
        facts = detect_project_facts(FIXTURES / "maven-only")
        self.assertEqual(facts.language.value, "java")
        self.assertEqual(facts.build_tool.value, "maven")
        self.assertEqual(facts.framework.value, "spring-boot")
        self.assertTrue(facts.capabilities.spring_web.value)
        self.assertTrue(facts.capabilities.layered_jar.value)
        self.assertEqual(facts.language.confidence, "high")
        self.assertTrue(facts.framework.evidence)

    def test_spring_gradle_fixture(self) -> None:
        facts = detect_project_facts(FIXTURES / "gradle-only")
        self.assertEqual(facts.build_tool.value, "gradle")
        self.assertEqual(facts.framework.value, "spring-boot")

    def test_plain_java_maven_fixture(self) -> None:
        facts = detect_project_facts(FIXTURES / "plain-java-maven")
        self.assertEqual(facts.framework.value, "plain-java")
        self.assertEqual(facts.build_tool.value, "maven")
        self.assertEqual(facts.java_version.value, 17)
        self.assertFalse(facts.capabilities.layered_jar.value)
        self.assertEqual(facts.packaging.value, "jar")

    def test_plain_java_gradle_fixture(self) -> None:
        facts = detect_project_facts(FIXTURES / "plain-java-gradle")
        self.assertEqual(facts.framework.value, "plain-java")
        self.assertEqual(facts.build_tool.value, "gradle")
        self.assertEqual(facts.java_version.value, 17)
        self.assertFalse(facts.capabilities.layered_jar.value)

    def test_cli_build_tool_overrides_detection(self) -> None:
        root = FIXTURES / "maven-only"
        facts = detect_project_facts(root, explicit_build_tool="maven")
        self.assertEqual(facts.build_tool.source, "cli")
        self.assertEqual(facts.build_tool.confidence, "high")

    def test_plugin_seed_implies_java_maven(self) -> None:
        seeded = seed_implied_facts(build_tool="maven")
        facts = detect_project_facts(FIXTURES / "plain-java-maven", seeded=seeded)
        self.assertEqual(facts.language.source, "plugin_seed")
        self.assertEqual(facts.build_tool.source, "plugin_seed")
        self.assertEqual(facts.framework.value, "plain-java")

    def test_override_fact_config_wins(self) -> None:
        facts = detect_project_facts(FIXTURES / "plain-java-maven")
        overridden = override_fact(facts.java_version, 21, source="config", evidence="java_version in .dockly.toml")
        self.assertEqual(overridden.value, 21)
        self.assertEqual(overridden.source, "config")

    def test_plugin_seed_spring_boot_maven(self) -> None:
        """Maven plugin surface: seed java+maven; detect Spring from fixture."""
        seeded = seed_implied_facts(build_tool="maven")
        facts = detect_project_facts(FIXTURES / "maven-only", seeded=seeded)
        self.assertEqual(facts.language.value, "java")
        self.assertEqual(facts.language.source, "plugin_seed")
        self.assertEqual(facts.build_tool.value, "maven")
        self.assertEqual(facts.build_tool.source, "plugin_seed")
        self.assertEqual(facts.framework.value, "spring-boot")
        self.assertEqual(facts.framework.source, "detected")
        self.assertTrue(facts.capabilities.layered_jar.value)

    def test_plugin_seed_plain_java_maven(self) -> None:
        """Maven plugin surface: seed java+maven; detect plain-java from fixture."""
        seeded = seed_implied_facts(build_tool="maven")
        facts = detect_project_facts(FIXTURES / "plain-java-maven", seeded=seeded)
        self.assertEqual(facts.language.source, "plugin_seed")
        self.assertEqual(facts.build_tool.source, "plugin_seed")
        self.assertEqual(facts.framework.value, "plain-java")
        self.assertEqual(facts.framework.source, "detected")
        self.assertFalse(facts.capabilities.layered_jar.value)

    def test_to_dict_shape(self) -> None:
        payload = detect_project_facts(FIXTURES / "maven-only").to_dict()
        self.assertIn("framework", payload)
        self.assertIn("confidence", payload["framework"])
        self.assertIn("evidence", payload["framework"])
        self.assertIn("capabilities", payload)


if __name__ == "__main__":
    unittest.main()
