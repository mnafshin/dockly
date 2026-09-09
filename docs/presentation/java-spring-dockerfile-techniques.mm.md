---
title: Java + Spring Dockerfile Techniques
markmap:
  colorFreezeLevel: 2
  maxWidth: 320
  initialExpandLevel: 2
---

# Java + Spring Dockerfiles

## Why containerize Spring apps?
- Consistent runtime across environments
- Packaged JVM + app + deps as one artifact
- Fits K8s / Cloud Run / ECS deployments
- Tradeoffs: image size, build time, cache reuse, security surface

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
### Typical sketch
- `FROM eclipse-temurin:21-jre`
- `COPY target/app.jar /app.jar`
- `ENTRYPOINT ["java","-jar","/app.jar"]`
### Pros
- Simplest to understand
- Few moving parts
### Cons
- Fat JAR = one huge layer
- Any code change invalidates the whole JAR layer
- Easy to ship JDK by mistake
- Weak caching for CI / registries

---

## 2. Multi-stage Dockerfile (build inside Docker)
### Idea
- Stage 1: JDK + Maven/Gradle → produce JAR
- Stage 2: JRE-only image → copy JAR and run
### Why it helps
- Final image has no Maven, no source, no build cache
- Reproducible builds in CI without host JDK
### Common bases (build)
- `maven:3.9-eclipse-temurin-21`
- `gradle:8-jdk21`
### Common bases (runtime)
- `eclipse-temurin:21-jre`
- `amazoncorretto:21-al2023-headless`
- Alpine / Distroless variants (see Base images)
### Pros
- Self-contained build
- Smaller runtime than single-stage JDK images
### Cons
- Without layering, still one fat JAR layer
- Slow if dependency download not cached well

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
### Dockerfile pattern
1. Builder: produce or copy uber-JAR
2. Extract layers with jarmode
3. Runtime: `COPY` layers in order (deps → loader → snapshots → app)
4. `ENTRYPOINT` via `JarLauncher` or `java -jar`
### Pros
- Best cache hit rate for classic JVM images
- Official Spring-recommended Dockerfile path
- Layout is CDS / AOT-cache friendly
### Cons
- More Dockerfile complexity
- Still a JVM image (size/startup vs native)

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
### When to choose
- Teams that want convention over configuration
- Spring Boot plugin already in the project

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
### When to choose
- Polyrepo Java services in CI
- Need daemonless image builds

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

---

## 7. Native Image (GraalVM)
### Idea
- Ahead-of-time compile Spring Boot (AOT) to a native binary
- Dockerfile copies binary into a tiny runtime (or uses buildpacks)
### Multi-stage sketch
- Build stage: GraalVM + native-image build
- Runtime: `scratch` / distroless / static musl image + binary
### Pros
- Very small images
- Instant / near-instant startup
- Lower memory for many services
### Cons
- Longer builds
- Reflection / resources need hints (Spring AOT helps a lot)
- Some libraries / agents unsupported
### Via Buildpacks
- Set `BP_NATIVE_IMAGE=true` instead of hand-rolling Graal Dockerfile

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

---

## 12. Quick decision guide
### “Just make it work”
→ Naive fat JAR on Temurin JRE
### “Fast CI deploys, keep Dockerfile”
→ Multi-stage + layered JAR (`jarmode`)
### “No Dockerfile, Spring-native DX”
→ `spring-boot:build-image` (Buildpacks)
### “Daemonless CI, Java-centric”
→ Jib
### “Tiny + fast cold start”
→ GraalVM Native Image (Dockerfile or Buildpacks)
### “Tune JVM startup further”
→ Layered image + CDS / AOT cache training run

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
