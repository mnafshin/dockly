# dockly GitHub Action

Composite Action that installs [dockly](https://pypi.org/project/dockly/), regenerates the Dockerfile from `.dockly.toml`, and fails the job when config drift is detected.

## Usage

```yaml
name: Dockerfile SSOT
on: [pull_request, push]
jobs:
  dockerfile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: mnafshin/dockly/action@v0
        with:
          project-root: .
          dockerfile: Dockerfile.generated
          # Optional: pin the CLI version (setup --ci does this automatically)
          # dockly-version: "0.1.0"
```

Or generate this workflow locally:

```bash
dockly setup --ci
# existing project:
dockly setup --ci-only
```

Generated workflows install the latest PyPI `dockly` by default. Add `dockly-version` under `with:` to pin.

## Inputs

| Input | Default | Description |
|---|---|---|
| `project-root` | `.` | Spring Boot project root |
| `dockerfile` | `Dockerfile.generated` | Dockerfile path relative to project root |
| `build-tool` | _(empty)_ | `maven` or `gradle`; empty = auto-detect |
| `dockly-version` | _(empty)_ | Pin PyPI `dockly` version; empty = latest |
| `python-version` | `3.11` | Python on the runner |
| `generate` | `true` | Run `dockerfile generate` |
| `check-config-drift` | `true` | Run `verify --check-config-drift` |

## Marketplace / versioning

Reference this Action by path (works on any tagged release of this repository):

```text
mnafshin/dockly/action@v0
mnafshin/dockly/action@v0.1.0
```

Publish a GitHub Release that includes this `action/` directory. Keep a moving `v0` major tag for consumers while on the 0.x line. Full marketplace listing can use the same release; the Action metadata lives in `action/action.yml` (path-based `uses:`).

Requires committed `.dockly.toml` and (when `include_embedded_sbom = true`) an `sbom.spdx.json` in the consumer repository. See [docs/adopt.md](../docs/adopt.md).
