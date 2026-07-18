# Migrating from springdocker to dockly

dockly is a **clean-import successor** to [`springdocker`](https://github.com/mnafshin/springdocker)
([ADR 0011](adr/0011-dockly-product-vision.md)). This guide covers the optional compatibility window
([#9](https://github.com/mnafshin/dockly/issues/9)).

## Quick map

| springdocker | dockly |
|---|---|
| `pipx install springdocker` / CLI `springdocker` | `pipx install dockly` / CLI `dockly` |
| `.springdocker.toml` | `.dockly.toml` |
| `SPRINGDOCKER_*` | `DOCKLY_*` |
| `import springdocker` / `springdocker.*` entry points | `import dockly` / `dockly.*` |
| Action `springdocker-version` | `dockly-version` |
| `springdocker-maven-plugin` / `mvn springdocker:*` | `dockly-maven-plugin` / `mvn dockly:*` |
| Gradle id `io.github.mnafshin.springdocker` | `io.github.mnafshin.dockly` |

Full table: [`CHANGELOG.md`](../CHANGELOG.md) (Unreleased → Migration).

## Shim policy (what is / is not shimmed)

Because dockly is a **new repository and package**, shims are intentionally **narrow**:

| Shimmed (deprecation window) | Not shimmed |
|---|---|
| Read `.springdocker.toml` when `.dockly.toml` is absent (warning on stderr) | Publishing dual PyPI names forever |
| Honor `SPRINGDOCKER_DISABLE_PLUGINS` / `SPRINGDOCKER_LEGACY_SCRIPTS` | Auto-rewrite of committed workflows to the new Action |
| Discover legacy `springdocker.*` entry-point groups | Keeping `springdocker` console script as a permanent alias |
| Docs + this migration guide | In-place Git history rewrite of the legacy springdocker repo |

**Recommended:** rename config to `.dockly.toml`, update CI to `dockly`, and remove legacy env vars when convenient.

## Config fallback

```bash
# Still works if only the legacy file exists:
dockly doctor
# → warning: using legacy config .springdocker.toml; rename to .dockly.toml
```

New writes (`init` / `setup` / `configure`) create **`.dockly.toml` only**.

## Legacy springdocker repository

The springdocker GitHub repo remains available for historical clones. New work happens in
[`mnafshin/dockly`](https://github.com/mnafshin/dockly). Point README / bookmarks here when you migrate.
