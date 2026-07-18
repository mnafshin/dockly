# dockly Maven Plugin (Java builder)

Pure-Java **builder plugin**. **POM `<configuration>` is SSOT** ([ADR 0010](../../docs/adr/0010-pom-gradle-ssot-java-builder.md)).

- Does **not** require Python, `pipx`, or `uv`
- Does **not** read `.dockly.toml` for generate/verify
- Benchmarks and advanced toolkit stay on the [Python CLI](../../cli/README.md)

## Configuration schema (v1)

| Parameter | Property | Type | Default | Effect |
|---|---|---|---|---|
| `javaVersion` | `dockly.javaVersion` | int | `17` | JDK major used in build/runtime image tags (`>= 17`) |
| `runtimeImage` | `dockly.runtimeImage` | enum | `distroless` | Runtime base: `distroless`, `debian-slim`, `alpine`, `ubuntu`, `temurin` |
| `useJlink` | `dockly.useJlink` | boolean | `true` | Custom jlink runtime stage (ignored when `runtimeImage=temurin` fat JRE path may still apply) |
| `useLayeredJar` | `dockly.useLayeredJar` | boolean | `true` | Spring Boot layered JAR extraction |
| `nonRoot` | `dockly.nonRoot` | boolean | `true` | Run as non-root USER where the base supports it |
| `recipe` | `dockly.recipe` | enum | `jvm-balanced` | `jvm-balanced` or `spring-aot` (`native-aot` is **CLI-only**) |
| `output` | `dockly.output` | string | `Dockerfile.generated` | Output Dockerfile path relative to project basedir |
| `skip` | `dockly.skip` | boolean | `false` | Skip Mojo execution |

### Explicitly out of plugin config

Benchmarks, configure wizard, full CLI profile matrix (`production-balanced`, …), digest-pin Renovate workflows, `setup --ci`. Use the Python CLI + `.dockly.toml` for those.

### Mapping notes (plugin → Dockerfile behavior)

| Plugin option | Dockerfile behavior (subset parity with CLI) |
|---|---|
| `javaVersion` | Selects Temurin JDK/JRE major tags in build (and runtime when applicable) |
| `runtimeImage=distroless` | Distroless nonroot runtime; no Dockerfile `HEALTHCHECK` |
| `runtimeImage=temurin` | Eclipse Temurin JRE runtime; simplest path |
| `runtimeImage=debian-slim\|alpine\|ubuntu` | Slim OS runtime (+ optional jlink when `useJlink=true`) |
| `useJlink=true` | Multi-stage jlink custom JRE (when not using plain temurin fat runtime) |
| `useLayeredJar=true` | `layertools` extract + layered `COPY` |
| `recipe=spring-aot` | Enables Spring AOT processing flags in the build stage |
| `nonRoot=true` | `USER` non-root (or distroless nonroot image) |

**SSOT rule:** generate reads **only** these Mojo parameters / defaults. It never opens `.dockly.toml`.

Canonical type: `io.github.mnafshin.dockly.maven.PluginDockerfileOptions`.

Implied facts (do not re-ask): `language=java`, `build_tool=maven`. Details: [`docs/plugin-facts.md`](../../docs/plugin-facts.md).

## Example

```xml
<plugin>
  <groupId>io.github.mnafshin</groupId>
  <artifactId>dockly-maven-plugin</artifactId>
  <version>0.1.0-SNAPSHOT</version>
  <configuration>
    <javaVersion>21</javaVersion>
    <runtimeImage>temurin</runtimeImage>
    <useJlink>false</useJlink>
    <useLayeredJar>true</useLayeredJar>
    <nonRoot>true</nonRoot>
    <recipe>jvm-balanced</recipe>
    <output>Dockerfile.generated</output>
  </configuration>
</plugin>
```

## Goals (roadmap)

| Goal | Status |
|---|---|
| `generate` | Implemented (pure Java; no Python) |
| `verify` | Implemented — fails on drift vs POM config |
| `export-config` | Implemented — optional one-way POM → `.dockly.toml` |

```bash
mvn dockly:generate
mvn dockly:verify
mvn dockly:export-config -Ddockly.force=true   # optional CLI bridge
```

Unlike the Python CLI (`verify --check-config-drift` against `.dockly.toml`), this Mojo checks the Dockerfile against **plugin `<configuration>` only**.

### Optional toml export

`export-config` writes `.dockly.toml` from plugin options so teams can later adopt the Python CLI. Re-export overwrites only with `-Ddockly.force=true`. Plugin configuration remains SSOT for the builder path.

## Migration from springdocker-maven-plugin

| Before | After |
|---|---|
| `io.github.mnafshin:springdocker-maven-plugin` | `io.github.mnafshin:dockly-maven-plugin` |
| `mvn springdocker:generate` / `verify` / `export-config` | `mvn dockly:generate` / `verify` / `export-config` |
| `-Dspringdocker.*` | `-Ddockly.*` |
| Package `io.github.mnafshin.springdocker.maven` | `io.github.mnafshin.dockly.maven` |

POM `<configuration>` element names (`javaVersion`, `runtimeImage`, …) are unchanged. ADR 0010 SSOT rules are unchanged: generate/verify still require neither Python nor `.dockly.toml`.

## Develop

```bash
cd integrations/maven-plugin
mvn test
```

Maven Central publishing: see [PUBLISHING.md](PUBLISHING.md) ([#145](https://github.com/mnafshin/dockly/issues/145)).
