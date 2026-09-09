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

## Baseline
- Spring Boot **3.3+** (`jarmode=tools`; older docs used `layertools`)
- Most examples: Java **21**
- Custom JRE / kitchen sink / AOT cache: Java **25**

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
### Needs
- Spring Boot **3.3+** (`-Djarmode=tools`)
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
# Official layout: extract --layers (no --launcher)
FROM eclipse-temurin:21-jre AS builder
WORKDIR /builder
ARG JAR_FILE=target/*.jar
COPY ${JAR_FILE} application.jar
RUN java -Djarmode=tools -jar application.jar extract \
    --layers --destination extracted

FROM eclipse-temurin:21-jre
WORKDIR /application
COPY --from=builder /builder/extracted/dependencies/ ./
COPY --from=builder /builder/extracted/spring-boot-loader/ ./
COPY --from=builder /builder/extracted/snapshot-dependencies/ ./
COPY --from=builder /builder/extracted/application/ ./
# Thin application.jar + lib/ — not JarLauncher
ENTRYPOINT ["java","-jar","application.jar"]
```
### Note
- `--launcher` → `JarLauncher` classpath layout (different ENTRYPOINT)
- Default (above) → thin `application.jar` + `lib/` (CDS/AOT friendly)

---

## 4. Base images
### General-purpose JRE
- glibc, fewest surprises
- Eclipse Temurin (Adoptium)
- Amazon Corretto
- Azul Zulu
### Alpine (musl)
- Smaller; watch DNS, JNI, agents
### Distroless / Chainguard
- Minimal attack surface, **no shell** in the prod image
- `docker exec … sh` fails by design — debug from the outside
- Local: `docker debug <container>` (Docker Desktop / Debug)
- K8s: `kubectl debug -it POD --image=busybox --target=APP`
- Ephemeral debug tools; image stays minimal
### See also
- Digest pin, JRE-only → Hardening
### Example
```dockerfile
FROM eclipse-temurin:21-jre
COPY app.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```

---

## 5. Build cache & CI
### Order layers by volatility
- `pom.xml` first, then sources
### BuildKit cache mounts
- Reuse `~/.m2` across builds on the **same** BuildKit builder
### `.dockerignore`
- Always drop `.git`, IDE files, docs
- Drop `target/` only when the Dockerfile **builds inside** Docker
- Keep `target/*.jar` in context for prebuilt-JAR Dockerfiles (§1, §3)
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
- GHA cache = **image layers**, not the `~/.m2` BuildKit mount

---

## 6. Startup accelerators
### CDS
- Training run in the Dockerfile
- Start with `-XX:SharedArchiveFile`
- Works on Java 21–25; prefer AOT cache when available
### AOT cache
- HotSpot (Java 24+; one-step `-XX:AOTCacheOutput` on **25+**)
- Same training-run pattern as CDS
### Spring AOT
- Build: `spring-boot:process-aot` (after `compile`)
- Runtime JVM: `-Dspring.aot.enabled=true`
- Less reflection at runtime (JVM or native)
### Example (CDS, after layered COPY)
```dockerfile
RUN java -XX:ArchiveClassesAtExit=application.jsa \
    -Dspring.context.exit=onRefresh \
    -jar application.jar
ENTRYPOINT ["java","-XX:SharedArchiveFile=application.jsa",\
  "-jar","application.jar"]
```

---

## 7. Custom JRE (`jdeps` + `jlink`)
### Idea
- Don't ship a full JDK/JRE distribution
- `jdeps` finds required modules → `jlink` builds a minimal runtime
- Final image = slim OS + custom JRE + app
### Tradeoff
- + Smaller image, fewer unused modules / CVEs
- + Pairs well with layered JAR + AOT cache
- − Extra build stage; module list needs care
- − Native agents / optional modules easy to miss
### Flow
1. Extract layered JAR (don't jdeps the fat JAR)
2. `jdeps --print-module-deps` on thin jar + `lib/*`
3. `jlink --add-modules … --output /javaruntime`
4. Runtime stage: copy `/javaruntime` + app only
### Tip
- Train AOT cache / CDS with the **same** custom JRE you ship
- Keep a **custom module list** for what `jdeps` misses
  (reflection, `ServiceLoader`, JNI, optional JDBC/XML/security modules)
- Merge: `jdeps` output ∪ curated baseline → feed `jlink`
### Example
```dockerfile
FROM eclipse-temurin:25-jdk AS jre
WORKDIR /work
COPY target/*.jar application.jar
RUN java -Djarmode=tools -jar application.jar extract \
      --layers --destination extracted \
 && jdeps --ignore-missing-deps -q --recursive --multi-release 25 \
      --print-module-deps \
      --class-path 'extracted/dependencies/lib/*' \
      extracted/application/application.jar \
      > /tmp/deps.txt \
 && echo "java.base,java.logging,java.xml,java.naming,java.desktop,\
java.management,java.security.jgss,java.instrument,jdk.unsupported,\
java.net.http,jdk.crypto.ec,java.sql,java.transaction.xa,\
java.rmi,jdk.jfr,jdk.management" > /tmp/base.txt \
 && MODULES=$(cat /tmp/deps.txt /tmp/base.txt | tr ',' '\n' \
      | tr -d ' ' | sort -u | paste -sd,) \
 && jlink --add-modules "$MODULES" \
      --strip-debug --no-man-pages --no-header-files --compress=zip-6 \
      --output /javaruntime

FROM debian:bookworm-slim
COPY --from=jre /javaruntime /opt/java
ENV PATH="/opt/java/bin:${PATH}"
WORKDIR /application
COPY --from=jre /work/extracted/dependencies/ ./
COPY --from=jre /work/extracted/spring-boot-loader/ ./
COPY --from=jre /work/extracted/snapshot-dependencies/ ./
COPY --from=jre /work/extracted/application/ ./
ENTRYPOINT ["java","-jar","application.jar"]
```

---

## 8. Hardening
### Identity & process
- Non-root **numeric** `USER` before ENTRYPOINT
- Exec-form ENTRYPOINT (SIGTERM reaches JVM)
  — not `ENTRYPOINT java -jar /app.jar`
  — use `ENTRYPOINT ["java","-jar","/app.jar"]`
- Drop Linux caps; no `--privileged`
```yaml
# Compose / K8s idea
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  capabilities: { drop: ["ALL"] }
```
### Image surface
- Runtime = **JRE**, never JDK
- Prefer Distroless / Chainguard / slim bases
- Multi-stage: no Maven, source, or build cache in final image
```dockerfile
# bad:  FROM eclipse-temurin:21-jdk
# good: FROM eclipse-temurin:21-jre
```
### Digest pin
- Pin `FROM ...@sha256:…` in production
- Avoid floating tags (`latest`, `21-jre`) for prod
```dockerfile
FROM eclipse-temurin:21-jre@sha256:abc123…
```
### SBOM & provenance
- SBOM = what's inside; provenance = how it was built
- Prefer BuildKit-generated attestations on push
```bash
# Needs container driver + registry push
docker buildx build --sbom=true --provenance=true \
  -t ghcr.io/acme/demo:1.2.3 --push .

# Optional extra SBOM export
syft ghcr.io/acme/demo:1.2.3 -o spdx-json > sbom.spdx.json

# Sign + verify image
cosign sign --yes ghcr.io/acme/demo@sha256:…
cosign verify ghcr.io/acme/demo@sha256:…

# Verify BuildKit provenance (don't hand-author if buildx emitted it)
cosign verify-attestation --type slsaprovenance \
  ghcr.io/acme/demo@sha256:…
```
### Scan
- CVE scan in CI (Trivy, Grype, registry scanners)
- Fail the pipeline on high/critical
```bash
trivy image --exit-code 1 --severity HIGH,CRITICAL demo:1.2.3
grype demo:1.2.3 --fail-on high
```
### Secrets & FS
- Read-only root FS (+ writable tmp if needed)
- Never bake secrets into `ENV` / layers
- Mount secrets at runtime (K8s secrets, CSI, Vault)
```yaml
# bad:  ENV DB_PASSWORD=s3cret
# good: runtime mount / env from Secret
volumeMounts: [{ name: db, mountPath: /run/secrets/db }]
readOnlyRootFilesystem: true
```
### JVM in containers
- `-XX:MaxRAMPercentage=75.0`, not fixed `-Xmx`
```dockerfile
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0"
```
### Example (Dockerfile)
```dockerfile
FROM eclipse-temurin:21-jre@sha256:REPLACE_WITH_REAL_DIGEST
WORKDIR /app
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app app
COPY --chown=10001:10001 target/*.jar app.jar
USER 10001
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0"
ENTRYPOINT ["java","-jar","/app/app.jar"]
```

---

## 9. Kitchen sink (Java 25 JVM path)
### Combines in one Dockerfile
- Multi-stage + BuildKit cache
- Spring AOT (`process-aot` + `-Dspring.aot.enabled=true`)
- Layered JAR (`jarmode`)
- Custom JRE (`jdeps` → `jlink`)
- HotSpot **AOT cache** (no CDS)
- Hardening: numeric non-root, `MaxRAMPercentage`, slim base
### Companion steps (CI — not in the Dockerfile)
- SBOM, provenance, sign, scan
### Not in the same file
- Buildpacks / Jib (replace the Dockerfile)
- GraalVM Native (different runtime)
### Example
```dockerfile
# syntax=docker/dockerfile:1
# Java 25: Spring AOT + layered + jdeps/jlink + AOT cache + hardening

FROM maven:3.9-eclipse-temurin-25 AS build
WORKDIR /src
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B dependency:go-offline
COPY src ./src
# compile before process-aot; package produces the boot jar
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -DskipTests compile spring-boot:process-aot package

FROM eclipse-temurin:25-jdk AS extractor
WORKDIR /builder
COPY --from=build /src/target/*.jar application.jar
RUN java -Djarmode=tools -jar application.jar extract \
    --layers --destination extracted

FROM eclipse-temurin:25-jdk AS jre
WORKDIR /work
COPY --from=extractor /builder/extracted /work/extracted
RUN jdeps --ignore-missing-deps -q --recursive --multi-release 25 \
      --print-module-deps \
      --class-path 'extracted/dependencies/lib/*' \
      extracted/application/application.jar \
      > /tmp/deps.txt \
 && echo "java.base,java.logging,java.xml,java.naming,java.desktop,\
java.management,java.security.jgss,java.instrument,jdk.unsupported,\
java.net.http,jdk.crypto.ec,java.sql,java.transaction.xa,\
java.rmi,jdk.jfr,jdk.management" > /tmp/base.txt \
 && MODULES=$(cat /tmp/deps.txt /tmp/base.txt | tr ',' '\n' \
      | tr -d ' ' | sort -u | paste -sd,) \
 && jlink --add-modules "$MODULES" \
      --strip-debug --no-man-pages --no-header-files --compress=zip-6 \
      --output /javaruntime

FROM debian:bookworm-slim
COPY --from=jre /javaruntime /opt/java
ENV PATH="/opt/java/bin:${PATH}"
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0 -Dspring.aot.enabled=true"
WORKDIR /application

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app app

COPY --from=extractor --chown=10001:10001 \
  /builder/extracted/dependencies/ ./
COPY --from=extractor --chown=10001:10001 \
  /builder/extracted/spring-boot-loader/ ./
COPY --from=extractor --chown=10001:10001 \
  /builder/extracted/snapshot-dependencies/ ./
COPY --from=extractor --chown=10001:10001 \
  /builder/extracted/application/ ./

# AOT cache training — JAVA_TOOL_OPTIONS already matches runtime
RUN java -XX:AOTCacheOutput=app.aot \
      -Dspring.context.exit=onRefresh \
      -jar application.jar \
 && chown 10001:10001 app.aot

USER 10001
EXPOSE 8080
ENTRYPOINT ["java","-XX:AOTCache=app.aot","-jar","application.jar"]
```
### Companion example (CI)
```bash
docker buildx build --sbom=true --provenance=true \
  -t ghcr.io/acme/demo:1.2.3 --push .

syft ghcr.io/acme/demo:1.2.3 -o spdx-json > sbom.spdx.json
cosign sign --yes ghcr.io/acme/demo@sha256:…
cosign verify-attestation --type slsaprovenance \
  ghcr.io/acme/demo@sha256:…
trivy image --exit-code 1 --severity HIGH,CRITICAL \
  ghcr.io/acme/demo:1.2.3
```

---

## 10. Alternatives without a Dockerfile
### Buildpacks
- `./mvnw spring-boot:build-image` — Paketo builds the image for you
- + Zero Dockerfile maintenance; layering, non-root, SBOM baked in
- − Less control; config via env/bindings; heavy first builds
### Jib
- Maven/Gradle plugin builds/pushes OCI images (often daemonless)
- + Fast incremental layers; no Docker-in-Docker in CI
- − No arbitrary `RUN` steps; different mental model than Dockerfiles
### When to use
- Want convention over a hand-written Dockerfile
- Otherwise stay on multi-stage + layered JAR for full control

---

## 11. Native Image (GraalVM)
### Idea
- AOT-compile Spring Boot to a native binary
- Drop the binary into a tiny base
### Tradeoff
- + Tiny image, near-instant startup
- + Lower memory per service
- − Slow builds; reflection needs hints
- − Some libs / agents unsupported or painful
  (Java agents like Datadog/New Relic `-javaagent`,
  runtime bytecode gen like CGLIB/Byte Buddy,
  load-time weaving, dynamic classloading)
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

## 12. Decision guide
### Just make it work
- Fat JAR on Temurin JRE
### Fast CI, keep Dockerfile
- Multi-stage + layered `jarmode`
### Smaller JVM runtime
- Custom JRE via `jdeps` + `jlink`
### Squeeze JVM startup
- Prefer **AOT cache** on Java 25+ (`-XX:AOTCacheOutput`)
- CDS still fine on 21–25 when AOT cache isn't an option
### No Dockerfile
- Buildpacks (`spring-boot:build-image`) or Jib
### Tiny + fast cold start
- GraalVM Native Image
