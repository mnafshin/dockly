# Extension model

`dockly` supports runtime plugins through six Python entry-point groups. Architecture decision record: [`adr/0001-plugin-architecture.md`](adr/0001-plugin-architecture.md).

Language/framework Dockerfile optimizations use the **Strategy API** ([`strategies.md`](strategies.md)) — separate from these entry-point groups.
Capability gating matrix (layered / Spring jar / plain Java): [`capabilities.md`](capabilities.md).

## Extension points

| Entry-point group | Contract | Used by |
|---|---|---|
| `dockly.dockerfile_mutators` | `mutate_dockerfile(dockerfile_text, options) -> str` | Post-process generated Dockerfiles |
| `dockly.project_detectors` | `detect_build_tool(project_root) -> "maven" \| "gradle" \| None` | Build-tool detection override for exotic monorepos |
| `dockly.recipes` | entry-point name is recipe name; callable returns Dockerfile text | Custom `dockerfile generate --recipe ...` |
| `dockly.verifiers` | `verify(context) -> (status, detail)` or dict payload | Extra checks in `verify` command |
| `dockly.verify_renderers` | entry-point name is output format; callable `render(outcome) -> str` | Custom `verify --format ...` renderers |
| `dockly.commands` | `register(subparsers)` and parser `set_defaults(_plugin_handler=...)` | Add top-level CLI commands |

For multi-module Maven reactors and Gradle composites, start with [`project-detection.md`](project-detection.md) — built-in inspect reports `layout` and `spring_boot_modules`, and `project_detectors` plugins cover layouts static parsing cannot handle.

## Failure handling

- Plugin failures are isolated per plugin.
- The command keeps running with built-in behavior whenever possible.
- Warnings are emitted for failed plugin invocations.
- Set `DOCKLY_DISABLE_PLUGINS=1` to disable all plugin groups.
  (`SPRINGDOCKER_DISABLE_PLUGINS` is still honored during the deprecation window.)

## Reference plugins

See:

- `docs/examples/extensions/custom_dockerfile_mutator.py`
- `docs/examples/extensions/custom_project_detector.py`
- `docs/examples/extensions/maven_reactor_project_detector.py`
- `docs/examples/extensions/gradle_monorepo_project_detector.py`
- `docs/examples/extensions/custom_recipe.py`
- `docs/examples/extensions/custom_verifier.py`
- `docs/examples/extensions/custom_verify_renderer.py`
- `docs/examples/extensions/custom_command.py`

## Packaging example

```toml
[project.entry-points."dockly.dockerfile_mutators"]
company-label = "acme_plugins.mutators:CompanyLabelMutator"

[project.entry-points."dockly.project_detectors"]
mono-repo = "acme_plugins.detectors:detect_build_tool"

[project.entry-points."dockly.recipes"]
acme-jvm = "acme_plugins.recipes:render_recipe"

[project.entry-points."dockly.verifiers"]
license = "acme_plugins.verifiers:verify"

[project.entry-points."dockly.verify_renderers"]
acme-json = "acme_plugins.renderers:render"

[project.entry-points."dockly.commands"]
acme-doctor = "acme_plugins.commands:register"
```
