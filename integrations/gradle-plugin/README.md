# dockly Gradle Plugin

Pure-Java twin of the [Maven builder plugin](../maven-plugin/README.md). **`build.gradle` / `build.gradle.kts` is SSOT** ([ADR 0010](../../docs/adr/0010-pom-gradle-ssot-java-builder.md)).

- No Python / `.dockly.toml` required for generate/verify
- Same option subset as the Maven plugin
- Reuses `DockerfileRenderer` from the Maven module sources

## Apply

```kotlin
// settings.gradle.kts — until Plugin Portal publish, use includeBuild or mavenLocal
pluginManagement {
    includeBuild("../gradle-plugin") // from a sibling checkout layout, or publishToMavenLocal
}

plugins {
    id("io.github.mnafshin.dockly") version "1.3.0-SNAPSHOT"
}

dockly {
    javaVersion.set(21)
    runtimeImage.set("temurin")
    useJlink.set(false)
    useLayeredJar.set(true)
    nonRoot.set(true)
    recipe.set("jvm-balanced")
    output.set("Dockerfile.generated")
}
```

```bash
./gradlew docklyGenerate
./gradlew docklyVerify
```

## Migration from springdocker Gradle plugin

| Before | After |
|---|---|
| Plugin id `io.github.mnafshin.springdocker` | `io.github.mnafshin.dockly` |
| Extension `springdocker { }` | `dockly { }` |
| Tasks `springdockerGenerate` / `springdockerVerify` | `docklyGenerate` / `docklyVerify` |

Extension property names are unchanged. ADR 0010 SSOT rules are unchanged: generate/verify still require neither Python nor `.dockly.toml`.

## Develop

```bash
cd integrations/gradle-plugin
gradle test
# or: gradle build
```

Requires a local Gradle distribution (`gradle` on PATH) or the Gradle wrapper (not bundled here yet).
