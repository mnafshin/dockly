---
title: Java + Spring Dockerfile Techniques
markmap:
  colorFreezeLevel: 2
  maxWidth: 420
  initialExpandLevel: 2
---

# Java + Spring Dockerfiles

## Why containerize Spring apps?
- Consistent runtime across environments
- Packaged JVM + app + deps as one artifact
- Fits K8s / Cloud Run / ECS deployments
- Tradeoffs: image size, build time, cache reuse, security surface
### Example tradeoff
- Fat JAR image: simple, rebuilds ~150MB on every code change
- Layered image: first build similar size; later pushes often &lt;5MB

## Technique map (pick by goal)
- Full control → hand-written Dockerfile
- No Dockerfile → Buildpacks or Jib
- Smallest / fastest start → Native Image (+ optional CDS/AOT on JVM)
- Fast CI rebuilds → layered JAR + multi-stage

---

## 1. Naive fat-JAR Dockerfile
### Idea
- Build JAR outside Docker (or copy prebuilt JAR)
- Single `FROM` + `COPY` + `java -jar`
### Pros
- Simplest to understand
- Few moving parts
### Cons
- Fat JAR = one huge layer
- Any code change invalidates the whole JAR layer
- Easy to ship JDK by mistake
- Weak caching for CI / registries
### Example Dockerfile
```dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/demo-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java","-jar","/app/app.jar"]
```
### Example build & run
```bash
./mvnw -DskipTests package
docker build -t demo:naive .
docker run --rm -p 8080:8080 demo:naive
```

---

## 2. Multi-stage Dockerfile (build inside Docker)
### Idea
- Stage 1: JDK + Maven/Gradle → produce JAR
- Stage 2: JRE-only image → copy JAR and run
### Why it helps
- Final image has no Maven, no source, no build cache
- Reproducible builds in CI without host JDK
### Pros
- Self-contained build
- Smaller runtime than single-stage JDK images
### Cons
- Without layering, still one fat JAR layer
- Slow if dependency download not cached well
### Example (Maven)
```dockerfile
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
COPY src ./src
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java","-jar","/app/app.jar"]
```
### Example (Gradle)
```dockerfile
FROM gradle:8-jdk21 AS build
WORKDIR /src
COPY build.gradle settings.gradle ./
COPY src ./src
RUN gradle bootJar --no-daemon

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/build/libs/*.jar app.jar
ENTRYPOINT ["java","-jar","/app/app.jar"]
```
### Example build
```bash
docker build -t demo:multistage .
```

---

## 3. Spring Boot layered JAR + multi-stage
### Core idea
- Spring Boot packages layers with different change frequency
- Extract layers → each becomes a Docker layer
- Code changes rebuild only the thin `application` layer
### Default layers (change frequency ↑)
- `dependencies` — stable third-party libs
- `spring-boot-loader` — Boot launcher
- `snapshot-dependencies` — SNAPSHOT deps
- `application` — your classes / resources
### Extraction (modern Boot)
- `java -Djarmode=tools -jar app.jar extract --layers --destination extracted`
### Legacy note
- Older docs used `-Djarmode=layertools`
### Pros
- Best cache hit rate for classic JVM images
- Official Spring-recommended Dockerfile path
- Layout is CDS / AOT-cache friendly
### Cons
- More Dockerfile complexity
- Still a JVM image (size/startup vs native)
### Example Dockerfile (prebuilt JAR)
```dockerfile
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
ENTRYPOINT ["java","org.springframework.boot.loader.launch.JarLauncher"]
```
### Example Dockerfile (build + extract)
```dockerfile
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
COPY src ./src
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21-jre AS extractor
WORKDIR /builder
COPY --from=build /src/target/*.jar application.jar
RUN java -Djarmode=tools -jar application.jar extract \
    --layers --destination extracted

FROM eclipse-temurin:21-jre
WORKDIR /application
COPY --from=extractor /builder/extracted/dependencies/ ./
COPY --from=extractor /builder/extracted/spring-boot-loader/ ./
COPY --from=extractor /builder/extracted/snapshot-dependencies/ ./
COPY --from=extractor /builder/extracted/application/ ./
ENTRYPOINT ["java","org.springframework.boot.loader.launch.JarLauncher"]
```
### Example build
```bash
./mvnw -DskipTests package
docker build -t demo:layered .
```

---

## 4. Cloud Native Buildpacks (no Dockerfile)
### Idea
- `./mvnw spring-boot:build-image` or Gradle equivalent
- Paketo (or other) builder detects Java/Spring and layers automatically
### What you get “for free”
- JRE selection
- Layering
- Non-root user
- Memory calculator / JVM defaults
- SBOM in the image
### Pros
- Zero Dockerfile maintenance
- Strong defaults & security patches via builder updates
- Native image possible (`BP_NATIVE_IMAGE=true`)
### Cons
- Less control than a custom Dockerfile
- First builds pull large builder images
- Customization via env/bindings, not free-form shell
### Example (Maven CLI)
```bash
./mvnw -DskipTests spring-boot:build-image \
  -Dspring-boot.build-image.imageName=demo:buildpacks
```
### Example (Gradle CLI)
```bash
./gradlew bootBuildImage --imageName=demo:buildpacks
```
### Example (pom.xml snippet)
```xml
<plugin>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-maven-plugin</artifactId>
  <configuration>
    <image>
      <name>ghcr.io/acme/demo:${project.version}</name>
      <env>
        <BPE_APPEND_JAVA_TOOL_OPTIONS>
          -XX:MaxRAMPercentage=75.0
        </BPE_APPEND_JAVA_TOOL_OPTIONS>
      </env>
    </image>
  </configuration>
</plugin>
```
### Example (native via Buildpacks)
```bash
./mvnw -DskipTests spring-boot:build-image \
  -Dspring-boot.build-image.environment.BP_NATIVE_IMAGE=true
```

---

## 5. Google Jib (no Dockerfile, no daemon optional)
### Idea
- Maven/Gradle plugin builds OCI image directly
- Layers deps vs classes automatically
- Can push without local Docker daemon (`jib:build`)
### Pros
- Fast incremental builds
- Great for CI without Docker-in-Docker
- Sensible Java layering out of the box
### Cons
- Less flexible than arbitrary Dockerfile RUN steps
- Learning curve for advanced config (entrypoint, volumes, auth)
### Example (pom.xml plugin)
```xml
<plugin>
  <groupId>com.google.cloud.tools</groupId>
  <artifactId>jib-maven-plugin</artifactId>
  <version>3.4.4</version>
  <configuration>
    <to>
      <image>ghcr.io/acme/demo</image>
    </to>
    <container>
      <ports>
        <port>8080</port>
      </ports>
      <jvmFlags>
        <jvmFlag>-XX:MaxRAMPercentage=75.0</jvmFlag>
      </jvmFlags>
    </container>
  </configuration>
</plugin>
```
### Example commands
```bash
# Needs Docker daemon (loads into local Docker)
./mvnw compile jib:dockerBuild -Dimage=demo:jib

# Daemonless — push straight to a registry
./mvnw compile jib:build \
  -Dimage=ghcr.io/acme/demo:jib
```
### Example (Gradle)
```kotlin
plugins {
  id("com.google.cloud.tools.jib") version "3.4.4"
}
jib {
  to { image = "ghcr.io/acme/demo" }
  container {
    ports = listOf("8080")
    jvmFlags = listOf("-XX:MaxRAMPercentage=75.0")
  }
}
```

---

## 6. Base image strategies
### Full / general-purpose JRE
- Eclipse Temurin, Amazon Corretto, Liberica, Azul Zulu
- Good glibc compatibility, fewer “weird Alpine” issues
### Alpine (musl)
- Smaller footprint
- Watch for musl / native-lib quirks (DNS, JNI, some agents)
### Distroless
- Minimal attack surface (no shell/package manager)
- Harder to debug in-container (`kubectl exec` limited)
### Chainguard / secure minimal
- Frequently updated, signed, small CVE surface
### Rule of thumb
- Runtime = **JRE**, not JDK
- Pin digests or immutable tags in production
### Example: Temurin JRE
```dockerfile
FROM eclipse-temurin:21.0.4_7-jre
COPY app.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```
### Example: Alpine
```dockerfile
FROM eclipse-temurin:21-jre-alpine
COPY app.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```
### Example: Distroless
```dockerfile
FROM gcr.io/distroless/java21-debian12
COPY app.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```
### Example: pin by digest
```dockerfile
FROM eclipse-temurin:21-jre@sha256:REPLACE_WITH_REAL_DIGEST
```

---

## 7. Native Image (GraalVM)
### Idea
- Ahead-of-time compile Spring Boot (AOT) to a native binary
- Dockerfile copies binary into a tiny runtime (or uses buildpacks)
### Pros
- Very small images
- Instant / near-instant startup
- Lower memory for many services
### Cons
- Longer builds
- Reflection / resources need hints (Spring AOT helps a lot)
- Some libraries / agents unsupported
### Example multi-stage Dockerfile
```dockerfile
FROM ghcr.io/graalvm/native-image-community:21 AS build
WORKDIR /src
COPY . .
RUN ./mvnw -Pnative -DskipTests native:compile

FROM gcr.io/distroless/base-debian12
WORKDIR /app
COPY --from=build /src/target/demo /app/demo
EXPOSE 8080
ENTRYPOINT ["/app/demo"]
```
### Example (pom native profile)
```xml
<profile>
  <id>native</id>
  <build>
    <plugins>
      <plugin>
        <groupId>org.graalvm.buildtools</groupId>
        <artifactId>native-maven-plugin</artifactId>
      </plugin>
    </plugins>
  </build>
</profile>
```
### Example via Buildpacks
```bash
./mvnw -DskipTests spring-boot:build-image \
  -Dspring-boot.build-image.environment.BP_NATIVE_IMAGE=true \
  -Dspring-boot.build-image.imageName=demo:native
```

---

## 8. JVM startup accelerators in Docker
### Class Data Sharing (CDS)
- Training run in Dockerfile after layer extract
- Store shared archive; start with CDS flags
- Cuts warm-ish JVM startup
### AOT cache (newer HotSpot / Boot support)
- Training run generates AOT cache
- Pass cache args on `java` entrypoint
- Complements layered layout from jarmode
### Spring AOT (build-time)
- `spring-boot:process-aot` / native AOT processing
- Shrinks runtime reflection work (JVM or native)
### Example: CDS training in Dockerfile
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
# Training run creates the CDS archive
RUN java -XX:ArchiveClassesAtExit=application.jsa \
    -Dspring.context.exit=onRefresh \
    org.springframework.boot.loader.launch.JarLauncher
ENTRYPOINT ["java",\
  "-XX:SharedArchiveFile=application.jsa",\
  "org.springframework.boot.loader.launch.JarLauncher"]
```
### Example: Spring AOT process (build time)
```bash
./mvnw -DskipTests spring-boot:process-aot package
```

---

## 9. Build-cache & CI techniques
### Dependency layering in Dockerfile
- Copy `pom.xml` / `build.gradle*` first
- `RUN mvn dependency:go-offline` (or Gradle equivalent)
- Then copy sources and package
### BuildKit cache mounts
- `--mount=type=cache,target=/root/.m2`
- Speeds multi-stage Maven/Gradle builds dramatically
### .dockerignore
- Exclude `.git`, `target/`, IDE files, docs
- Keeps build context small
### Prebuilt JAR vs build-in-Docker
- Prebuilt: faster Docker step, needs host/CI Java build
- In-Docker: more hermetic, heavier Dockerfile
### Example: dep layer + BuildKit cache
```dockerfile
# syntax=docker/dockerfile:1
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B dependency:go-offline
COPY src ./src
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -DskipTests package

FROM eclipse-temurin:21-jre
COPY --from=build /src/target/*.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```
### Example: .dockerignore
```gitignore
.git
.idea
*.iml
target
build
.gradle
docs
*.md
```
### Example CI (GitHub Actions snippet)
```yaml
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v6
  with:
    context: .
    push: true
    tags: ghcr.io/acme/demo:latest
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

---

## 10. Runtime hardening checklist
### Process identity
- Create non-root user; `USER` before ENTRYPOINT
### JVM memory in containers
- Prefer `-XX:MaxRAMPercentage=75.0` over fixed `-Xmx`
- Container support is default on modern JDKs
### Signals & PID 1
- Proper ENTRYPOINT so SIGTERM reaches the JVM
- Avoid wrapping in unhandled shell unless needed
### Read-only & secrets
- Prefer read-only root FS where possible
- Never bake secrets into `ENV` / image layers
### Health
- Expose actuator/`/` health for orchestrators
- Keep probes lightweight
### Example hardened Dockerfile
```dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app app
COPY --chown=app:app target/*.jar app.jar
USER app
EXPOSE 8080
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0"
ENTRYPOINT ["java","-jar","/app/app.jar"]
```
### Example: Alpine non-root
```dockerfile
FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S app && adduser -S app -G app
WORKDIR /app
COPY --chown=app:app target/*.jar app.jar
USER app
ENTRYPOINT ["java","-XX:MaxRAMPercentage=75.0","-jar","/app/app.jar"]
```
### Example: K8s probes (actuator)
```yaml
livenessProbe:
  httpGet: { path: /actuator/health/liveness, port: 8080 }
readinessProbe:
  httpGet: { path: /actuator/health/readiness, port: 8080 }
securityContext:
  runAsNonRoot: true
  readOnlyRootFilesystem: true
```

---

## 11. Packaging variants that change the Dockerfile
### Uber / executable JAR (default)
- Most common; works with all techniques above
### Exploded / thin JAR
- Separate lib/ from classes; similar goals to layering
### War + external Tomcat
- Base = Tomcat image; drop WAR into `webapps/`
- Less common for greenfield Boot apps
### Modular / jlink custom JRE
- Build a minimal JRE with `jlink` in a builder stage
- Advanced size optimization on JVM path
### Example: uber JAR (default)
```dockerfile
FROM eclipse-temurin:21-jre
COPY target/demo.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```
### Example: exploded classpath layout
```dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/dependency/ ./lib/
COPY target/classes/ ./classes/
ENTRYPOINT ["java","-cp","classes:lib/*","com.example.DemoApplication"]
```
### Example: WAR on Tomcat
```dockerfile
FROM tomcat:10.1-jdk21-temurin
RUN rm -rf /usr/local/tomcat/webapps/*
COPY target/demo.war /usr/local/tomcat/webapps/ROOT.war
EXPOSE 8080
```
### Example: jlink custom JRE
```dockerfile
FROM eclipse-temurin:21-jdk AS jre-build
RUN jlink --add-modules java.base,java.logging,java.xml,\
    java.naming,java.desktop,java.management,java.security.jgss,\
    java.instrument,jdk.unsupported,java.net.http \
  --strip-debug --no-man-pages --no-header-files \
  --compress=2 --output /javaruntime

FROM debian:bookworm-slim
COPY --from=jre-build /javaruntime /opt/java
ENV PATH="/opt/java/bin:${PATH}"
COPY target/demo.jar /app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
```

---

## 12. Quick decision guide
### “Just make it work”
→ Naive fat JAR on Temurin JRE
#### Example
```bash
docker build -f Dockerfile.naive -t demo:simple .
```
### “Fast CI deploys, keep Dockerfile”
→ Multi-stage + layered JAR (`jarmode`)
#### Example
```bash
docker build -f Dockerfile.layered -t demo:layered .
```
### “No Dockerfile, Spring-native DX”
→ `spring-boot:build-image` (Buildpacks)
#### Example
```bash
./mvnw spring-boot:build-image -Dspring-boot.build-image.imageName=demo:cnb
```
### “Daemonless CI, Java-centric”
→ Jib
#### Example
```bash
./mvnw compile jib:build -Dimage=ghcr.io/acme/demo:jib
```
### “Tiny + fast cold start”
→ GraalVM Native Image (Dockerfile or Buildpacks)
#### Example
```bash
./mvnw -Pnative -DskipTests native:compile
```
### “Tune JVM startup further”
→ Layered image + CDS / AOT cache training run
#### Example
```bash
docker build -f Dockerfile.cds -t demo:cds .
```

---

## Reference commands (mental model)
### Buildpacks
- `./mvnw -DskipTests spring-boot:build-image`
### Jib
- `./mvnw compile jib:build` / `jib:dockerBuild`
### Layer extract
- `java -Djarmode=tools -jar app.jar extract --layers --destination extracted`
### Typical layered COPY order
1. `dependencies/`
2. `spring-boot-loader/`
3. `snapshot-dependencies/`
4. `application/`
