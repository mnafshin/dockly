"""Structured ProjectFacts detection for dockly.

Principles (see docs/project-facts.md):
1. Aggressive auto-detect from project markers
2. Config/CLI always wins over detected values (applied by callers)
3. Plugin surfaces may seed known facts (see seed_implied_facts)
4. inspect reports confidence + evidence per fact
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .project_detect import (
    analyze_multi_module_layout,
    detect_build_tool,
    inspect_project,
    inspect_project_details,
)

Confidence = str  # "high" | "medium" | "low" | "unknown"
FactSource = str  # "detected" | "cli" | "config" | "plugin_seed"


@dataclass(frozen=True)
class Fact:
    """One detected (or seeded) fact with confidence and evidence."""

    value: Any
    confidence: Confidence
    source: FactSource
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "evidence": list(self.evidence),
        }


def _fact(
    value: Any,
    *,
    confidence: Confidence,
    source: FactSource = "detected",
    evidence: tuple[str, ...] = (),
) -> Fact:
    return Fact(value=value, confidence=confidence, source=source, evidence=evidence)


@dataclass(frozen=True)
class ProjectCapabilities:
    layered_jar: Fact
    actuator: Fact
    spring_web: Fact

    def to_dict(self) -> dict[str, Any]:
        return {
            "layered_jar": self.layered_jar.to_dict(),
            "actuator": self.actuator.to_dict(),
            "spring_web": self.spring_web.to_dict(),
        }


@dataclass(frozen=True)
class ProjectFacts:
    """Canonical project facts consumed by strategies and inspect."""

    root: Path
    language: Fact
    build_tool: Fact
    java_version: Fact
    framework: Fact  # "spring-boot" | "plain-java"
    spring_boot_version: Fact
    project_kind: Fact  # "executable" | "library" | "multi-module" | "unknown"
    packaging: Fact  # jar | war | pom | unknown
    layout: Fact
    modules: tuple[str, ...]
    spring_boot_modules: tuple[str, ...]
    capabilities: ProjectCapabilities
    direct_dependencies: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "language": self.language.to_dict(),
            "build_tool": self.build_tool.to_dict(),
            "java_version": self.java_version.to_dict(),
            "framework": self.framework.to_dict(),
            "spring_boot_version": self.spring_boot_version.to_dict(),
            "project_kind": self.project_kind.to_dict(),
            "packaging": self.packaging.to_dict(),
            "layout": self.layout.to_dict(),
            "modules": list(self.modules),
            "spring_boot_modules": list(self.spring_boot_modules),
            "capabilities": self.capabilities.to_dict(),
            "direct_dependencies": list(self.direct_dependencies),
        }


def seed_implied_facts(
    *,
    build_tool: str,
    language: str = "java",
    source: FactSource = "plugin_seed",
) -> dict[str, Fact]:
    """Facts implied by a surface (e.g. Maven plugin ⇒ Java + Maven) without re-asking."""
    if build_tool not in {"maven", "gradle"}:
        raise ValueError("build_tool must be 'maven' or 'gradle'")
    if language != "java":
        raise ValueError("only language='java' is supported for first-party seeds")
    return {
        "language": _fact(language, confidence="high", source=source, evidence=(f"{build_tool} plugin surface",)),
        "build_tool": _fact(build_tool, confidence="high", source=source, evidence=(f"{build_tool} plugin surface",)),
    }


def _maven_packaging(root: Path) -> tuple[str, tuple[str, ...]]:
    pom = root / "pom.xml"
    if not pom.is_file():
        return "unknown", ()
    try:
        tree = ET.parse(pom)
        xml_root = tree.getroot()
        for el in xml_root.iter():
            if "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]
        packaging = (xml_root.findtext("packaging") or "jar").strip() or "jar"
        return packaging, (f"pom.xml packaging={packaging}",)
    except ET.ParseError:
        return "unknown", ("pom.xml parse error",)


def _dependency_names(deps: tuple[str, ...]) -> set[str]:
    names: set[str] = set()
    for dep in deps:
        # group:artifact or artifact
        if ":" in dep:
            names.add(dep.split(":", 1)[1])
        names.add(dep)
    return names


def _capability_facts(deps: tuple[str, ...], has_spring: bool, boot_version: str | None) -> ProjectCapabilities:
    names = _dependency_names(deps)
    has_actuator = "spring-boot-starter-actuator" in names or any("actuator" in d for d in deps)
    has_web = any(
        a in names
        for a in (
            "spring-boot-starter-web",
            "spring-boot-starter-webflux",
            "spring-boot-starter-websocket",
        )
    )
    layered = False
    layered_conf: Confidence = "unknown"
    layered_evidence: tuple[str, ...] = ()
    if has_spring:
        # Spring Boot 2.3+ supports layertools; treat any detected Boot as layered-capable with medium/high.
        layered = True
        if boot_version:
            major = boot_version.split(".", 1)[0]
            try:
                major_i = int(major)
            except ValueError:
                major_i = 0
            if major_i >= 3 or (major_i == 2 and _boot_minor(boot_version) >= 3):
                layered_conf = "high"
                layered_evidence = (f"Spring Boot {boot_version} supports layered JARs (layertools)",)
            else:
                layered_conf = "medium"
                layered_evidence = (f"Spring Boot {boot_version} present; layered JAR support uncertain",)
        else:
            layered_conf = "medium"
            layered_evidence = ("Spring Boot markers present; assume layered JAR capable",)
    else:
        layered_evidence = ("plain Java — no Spring Boot layered JAR path",)
        layered_conf = "high"

    return ProjectCapabilities(
        layered_jar=_fact(layered, confidence=layered_conf, evidence=layered_evidence),
        actuator=_fact(
            has_actuator,
            confidence="high" if has_actuator or deps else "low",
            evidence=(
                ("dependency spring-boot-starter-actuator",) if has_actuator else ("no actuator starter in direct deps",)
            ),
        ),
        spring_web=_fact(
            has_web,
            confidence="high" if has_web or deps else "low",
            evidence=(("Spring Web starter in direct deps",) if has_web else ("no Spring Web starter in direct deps",)),
        ),
    )


def _boot_minor(version: str) -> int:
    parts = version.split(".")
    if len(parts) < 2:
        return 0
    try:
        return int(parts[1])
    except ValueError:
        return 0


def _project_kind(
    *,
    layout: str,
    packaging: str,
    has_spring: bool,
) -> Fact:
    if layout in {"maven-reactor", "gradle-multi-project"}:
        return _fact(
            "multi-module",
            confidence="high",
            evidence=(f"layout={layout}",),
        )
    if has_spring:
        return _fact("executable", confidence="high", evidence=("Spring Boot markers ⇒ executable app",))
    if packaging == "pom":
        return _fact("multi-module", confidence="medium", evidence=("packaging=pom",))
    if packaging in {"jar", "war"}:
        # Plain Java jar/war — treat as executable candidate (main class not always detectable statically)
        return _fact(
            "executable",
            confidence="medium",
            evidence=(f"packaging={packaging} without Spring Boot markers",),
        )
    return _fact("unknown", confidence="low", evidence=("could not classify project kind",))


def detect_project_facts(
    root: Path,
    explicit_build_tool: str | None = None,
    *,
    seeded: dict[str, Fact] | None = None,
) -> ProjectFacts:
    """Detect ProjectFacts. Optional seeded facts (plugin surface) override detected equivalents."""
    root = root.resolve()
    seeded = seeded or {}

    # Build tool: CLI explicit > seed > detect
    if explicit_build_tool:
        build_tool_fact = _fact(
            explicit_build_tool,
            confidence="high",
            source="cli",
            evidence=(f"--build-tool {explicit_build_tool}",),
        )
        tool = explicit_build_tool
    elif "build_tool" in seeded:
        build_tool_fact = seeded["build_tool"]
        tool = str(build_tool_fact.value)
    else:
        tool = detect_build_tool(root, None)
        evidence = []
        if tool == "maven" and (root / "pom.xml").exists():
            evidence.append("pom.xml")
        if tool == "gradle":
            for name in ("gradlew", "build.gradle", "build.gradle.kts"):
                if (root / name).exists():
                    evidence.append(name)
        build_tool_fact = _fact(tool, confidence="high", evidence=tuple(evidence) or ("build markers",))

    project = inspect_project(root, tool)
    details = inspect_project_details(root, tool)
    layout = analyze_multi_module_layout(root, tool)

    if "language" in seeded:
        language_fact = seeded["language"]
    else:
        language_fact = _fact(
            "java",
            confidence="high",
            evidence=(f"{tool} Java project markers",),
        )

    java_evidence: list[str] = []
    java_conf: Confidence = "unknown"
    if details.java_version is not None:
        java_conf = "high"
        java_evidence.append(f"detected java_version={details.java_version}")
    else:
        java_evidence.append("java version not found in descriptors")

    has_spring = project.has_spring_markers
    if has_spring:
        framework_fact = _fact(
            "spring-boot",
            confidence="high",
            evidence=("spring-boot markers in descriptors or application.yml/properties",),
        )
    else:
        framework_fact = _fact(
            "plain-java",
            confidence="high",
            evidence=("no Spring Boot markers",),
        )

    boot_conf: Confidence = "high" if details.spring_boot_version else ("medium" if has_spring else "high")
    boot_evidence = (
        (f"spring_boot_version={details.spring_boot_version}",)
        if details.spring_boot_version
        else (("Spring Boot markers without version",) if has_spring else ("n/a for plain Java",))
    )

    packaging_value: str = "unknown"
    packaging_evidence: tuple[str, ...] = ()
    if tool == "maven":
        packaging_value, packaging_evidence = _maven_packaging(root)
    elif tool == "gradle":
        packaging_value, packaging_evidence = "jar", ("gradle default packaging assumed jar",)

    kind_fact = _project_kind(layout=layout.kind, packaging=packaging_value, has_spring=has_spring)
    caps = _capability_facts(details.direct_dependencies, has_spring, details.spring_boot_version)

    return ProjectFacts(
        root=root,
        language=language_fact,
        build_tool=build_tool_fact,
        java_version=_fact(details.java_version, confidence=java_conf, evidence=tuple(java_evidence)),
        framework=framework_fact,
        spring_boot_version=_fact(details.spring_boot_version, confidence=boot_conf, evidence=boot_evidence),
        project_kind=kind_fact,
        packaging=_fact(packaging_value, confidence="high" if packaging_value != "unknown" else "low", evidence=packaging_evidence),
        layout=_fact(layout.kind, confidence="high", evidence=(f"layout={layout.kind}",)),
        modules=layout.modules,
        spring_boot_modules=layout.spring_boot_modules,
        capabilities=caps,
        direct_dependencies=details.direct_dependencies,
    )


def override_fact(fact: Fact, value: Any, *, source: FactSource, evidence: str) -> Fact:
    """Apply config/CLI precedence: caller-supplied value always wins."""
    return _fact(value, confidence="high", source=source, evidence=(evidence,))


# Public API
__all__ = [
    "Fact",
    "ProjectCapabilities",
    "ProjectFacts",
    "detect_project_facts",
    "override_fact",
    "seed_implied_facts",
]
