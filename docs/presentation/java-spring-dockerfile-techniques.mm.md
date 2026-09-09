---
title: Java + Spring Dockerfile Techniques
markmap:
  colorFreezeLevel: 2
  maxWidth: 320
  initialExpandLevel: 2
---

# Java + Spring Dockerfiles

## Why it matters
- One artifact: JVM + app + deps
- Levers: size, build time, cache reuse, security
- Fat JAR: ~150MB pushed per code change
- Layered: often <5MB pushed per code change

---

## 1. Naive fat JAR
### Idea
- Prebuilt JAR → `COPY` → `java -jar`
### Tradeoff
- + Simplest possible
- − One huge layer, zero cache reuse
- − Easy to ship a JDK by mistake
### Example
```dockerfile
FROM eclipse-temurin:21-jre
COPY target/*.jar /app.jar
EXPOSE 8080
ENTRYPOINT ["java","-jar","/app.jar"]
```

---

## 2. Multi-stage
### Idea
- Stage 1: JDK + Maven → JAR
- Stage 2: JRE only → run
### Tradeoff
- + No Maven, source, or build cache in final image
- + Hermetic CI, no host JDK
- − Still one fat JAR layer
### Example
```dockerfile
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
COPY src ./src
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21-jre
COPY --from=build /src/target/*.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```

---

## 3. Layered JAR (`jarmode`)
### Idea
- Boot splits the JAR by change frequency
- Each layer → its own Docker layer
- Code change rebuilds only `application/`
### Layers (stable → volatile)
- `dependencies`
- `spring-boot-loader`
- `snapshot-dependencies`
- `application`
### Tradeoff
- + Best cache hit rate on the JVM path
- + Spring's recommended layout, CDS/AOT friendly
- − More Dockerfile complexity
### Example
```dockerfile
FROM eclipse-temurin:21-jre AS builder
WORKDIR /builder
COPY target/*.jar application.jar
RUN java -Djarmode=tools -jar application.jar extract \
    --layers --destination extracted

FROM eclipse-temurin:21-jre
WORKDIR /application
COPY --from=builder /builder/extracted/dependencies/ ./
COPY --from=builder /builder/extracted/spring-boot-loader/ ./
COPY --from=builder /builder/extracted/snapshot-dependencies/ ./
COPY --from=builder /builder/extracted/application/ ./
ENTRYPOINT ["java","org.springframework.boot.loader.launch.JarLauncher"]
```

---

## 4. Buildpacks
### Idea
- No Dockerfile — builder detects Spring and layers it
### Free defaults
- JRE choice, layering, non-root
- Memory calculator, SBOM
### Tradeoff
- + Zero Dockerfile maintenance
- + Patches arrive via builder updates
- − Config via env/bindings, not shell
### Example
```bash
./mvnw -DskipTests spring-boot:build-image \
  -Dspring-boot.build-image.imageName=demo:cnb
```

---

## 5. Jib
### Idea
- Maven/Gradle plugin builds OCI images directly
- Pushes without a Docker daemon
### Tradeoff
- + Fast incremental builds
- + No Docker-in-Docker in CI
- − No arbitrary `RUN` steps
### Example
```bash
./mvnw compile jib:build -Dimage=ghcr.io/acme/demo:jib
```

---

## 6. Base images
### Temurin / Corretto / Zulu
- glibc, fewest surprises
### Alpine (musl)
- Smaller; watch DNS, JNI, agents
### Distroless / Chainguard
- Minimal attack surface, no shell
- Harder to debug in-container
### See also
- Digest pin, JRE-only → Hardening
### Example
```dockerfile
FROM eclipse-temurin:21-jre
COPY app.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```

---

## 7. Native Image (GraalVM)
### Idea
- AOT-compile Spring Boot to a native binary
- Drop the binary into a tiny base
### Tradeoff
- + Tiny image, near-instant startup
- + Lower memory per service
- − Slow builds; reflection needs hints
- − Some libraries and agents unsupported
### Example
```dockerfile
FROM ghcr.io/graalvm/native-image-community:21 AS build
WORKDIR /src
COPY . .
RUN ./mvnw -Pnative -DskipTests native:compile

FROM gcr.io/distroless/base-debian12
COPY --from=build /src/target/demo /app/demo
EXPOSE 8080
ENTRYPOINT ["/app/demo"]
```

---

## 8. Startup accelerators
### CDS
- Training run in the Dockerfile
- Start with `-XX:SharedArchiveFile`
### AOT cache
- Newer HotSpot; same training-run pattern
### Spring AOT
- `spring-boot:process-aot`
- Less reflection at runtime (JVM or native)
### Example
```dockerfile
# after the layered COPY steps
RUN java -XX:ArchiveClassesAtExit=application.jsa \
    -Dspring.context.exit=onRefresh \
    org.springframework.boot.loader.launch.JarLauncher
ENTRYPOINT ["java","-XX:SharedArchiveFile=application.jsa",\
  "org.springframework.boot.loader.launch.JarLauncher"]
```

---

## 9. Build cache & CI
### Order layers by volatility
- `pom.xml` first, then sources
### BuildKit cache mounts
- Reuse `~/.m2` across builds
### `.dockerignore`
- Drop `.git`, `target`, IDE files, docs
### Example
```dockerfile
# syntax=docker/dockerfile:1
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 mvn -B dependency:go-offline
COPY src ./src
RUN --mount=type=cache,target=/root/.m2 mvn -B -DskipTests package

FROM eclipse-temurin:21-jre
COPY --from=build /src/target/*.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```
### CI cache
```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

---

## 10. Hardening
### Identity & process
- Non-root `USER` before ENTRYPOINT
- Exec-form ENTRYPOINT (SIGTERM reaches JVM)
- Drop Linux caps; no `--privileged`
### Image surface
- Runtime = **JRE**, never JDK
- Prefer Distroless / Chainguard / slim bases
- Multi-stage: no Maven, source, or build cache in final image
### Digest pin
- Pin `FROM ...@sha256:…` in production
- Avoid floating tags (`latest`, `21-jre`) for prod
### SBOM & provenance
- Emit SBOM (Syft, Buildpacks, `docker buildx --sbom`)
- Sign images (Cosign) + verify in deploy
- Prefer attested builds (SLSA / provenance)
### Scan
- CVE scan in CI (Trivy, Grype, registry scanners)
- Fail the pipeline on high/critical
### Secrets & FS
- Read-only root FS (+ writable tmp if needed)
- Never bake secrets into `ENV` / layers
- Mount secrets at runtime (K8s secrets, CSI, Vault)
### JVM in containers
- `-XX:MaxRAMPercentage=75.0`, not fixed `-Xmx`
### Example
```dockerfile
FROM eclipse-temurin:21-jre@sha256:REPLACE_WITH_REAL_DIGEST
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app app
COPY --chown=app:app target/*.jar app.jar
USER app
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0"
ENTRYPOINT ["java","-jar","/app/app.jar"]
```
### Example: SBOM + sign (CI)
```bash
syft demo:prod -o spdx-json > sbom.spdx.json
cosign sign --yes ghcr.io/acme/demo@sha256:…
```

---

## 11. Packaging variants
### Uber JAR
- Default; works with everything above
### Exploded / thin
- `lib/` split from `classes/`
### WAR + Tomcat
- Tomcat base, WAR into `webapps/`
- Rare for greenfield Boot
### jlink custom JRE
- Minimal runtime built in a builder stage
### Example
```dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/dependency/ ./lib/
COPY target/classes/ ./classes/
ENTRYPOINT ["java","-cp","classes:lib/*","com.example.DemoApplication"]
```

---

## 12. Decision guide
### Just make it work
- Fat JAR on Temurin JRE
### Fast CI, keep Dockerfile
- Multi-stage + layered `jarmode`
### No Dockerfile
- `spring-boot:build-image`
### Daemonless CI
- Jib
### Tiny + fast cold start
- GraalVM Native Image
### Squeeze JVM startup
- Layered + CDS/AOT training run

---

## 13. Kitchen sink (Java 21 JVM path)
### Combines in one Dockerfile
- Multi-stage + BuildKit cache
- Spring AOT (`process-aot`)
- Layered JAR (`jarmode`)
- `jdeps` → `jlink` custom JRE
- CDS training (Java 21)
- Hardening: non-root, `MaxRAMPercentage`, slim base
### Not in the same file
- Buildpacks / Jib (replace the Dockerfile)
- GraalVM Native (different runtime)
- HotSpot AOT cache → needs **Java 24+** (swap CDS block)
### Example
```dockerfile
# syntax=docker/dockerfile:1
# Java 21: Spring AOT + layered + jdeps/jlink + CDS + hardening

FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B dependency:go-offline
COPY src ./src
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -DskipTests spring-boot:process-aot package

FROM eclipse-temurin:21-jdk AS extractor
WORKDIR /builder
COPY --from=build /src/target/*-SNAPSHOT.jar application.jar
RUN java -Djarmode=tools -jar application.jar extract \
    --layers --destination extracted

FROM eclipse-temurin:21-jdk AS jre
WORKDIR /work
COPY --from=extractor /builder/extracted /work/extracted
# Resolve modules; fall back to a safe Spring set if jdeps is sparse
RUN jdeps --ignore-missing-deps -q --recursive --multi-release 21 \
      --print-module-deps \
      --class-path 'extracted/dependencies/BOOT-INF/lib/*' \
      extracted/application/BOOT-INF/classes \
      > /tmp/deps.txt 2>/dev/null || true \
 && echo "java.base,java.logging,java.xml,java.naming,java.desktop,\
java.management,java.security.jgss,java.instrument,jdk.unsupported,\
java.net.http,jdk.crypto.ec,java.sql,java.transaction.xa,\
java.rmi,jdk.jfr,jdk.management" > /tmp/base.txt \
 && MODULES=$(cat /tmp/deps.txt /tmp/base.txt | tr ',' '\n' \
      | tr -d ' ' | sort -u | paste -sd,) \
 && jlink --add-modules "$MODULES" \
      --strip-debug --no-man-pages --no-header-files --compress=2 \
      --output /javaruntime

FROM debian:bookworm-slim
COPY --from=jre /javaruntime /opt/java
ENV PATH="/opt/java/bin:${PATH}"
WORKDIR /application

RUN groupadd --system app && useradd --system --gid app app

COPY --from=extractor --chown=app:app \
  /builder/extracted/dependencies/ ./
COPY --from=extractor --chown=app:app \
  /builder/extracted/spring-boot-loader/ ./
COPY --from=extractor --chown=app:app \
  /builder/extracted/snapshot-dependencies/ ./
COPY --from=extractor --chown=app:app \
  /builder/extracted/application/ ./

# CDS training (same custom JRE as runtime)
RUN java -XX:ArchiveClassesAtExit=application.jsa \
      -Dspring.context.exit=onRefresh \
      org.springframework.boot.loader.launch.JarLauncher \
 && chown app:app application.jsa

USER app
EXPOSE 8080
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0"
ENTRYPOINT ["java","-XX:SharedArchiveFile=application.jsa",\
  "org.springframework.boot.loader.launch.JarLauncher"]
```
### Java 24+: swap CDS for AOT cache
```dockerfile
RUN java -XX:AOTMode=record -XX:AOTConfiguration=app.aotconf \
      -Dspring.context.exit=onRefresh \
      org.springframework.boot.loader.launch.JarLauncher \
 && java -XX:AOTMode=create -XX:AOTConfiguration=app.aotconf \
      -XX:AOTCache=app.aot \
      org.springframework.boot.loader.launch.JarLauncher \
 && rm app.aotconf && chown app:app app.aot
ENTRYPOINT ["java","-XX:AOTCache=app.aot",\
  "org.springframework.boot.loader.launch.JarLauncher"]
```
### After build (CI)
```bash
syft demo:prod -o spdx-json > sbom.spdx.json
cosign sign --yes ghcr.io/acme/demo@sha256:…
```
