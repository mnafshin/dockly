package io.github.mnafshin.dockly.gradle;

import io.github.mnafshin.dockly.maven.PluginDockerfileOptions;
import org.gradle.api.Plugin;
import org.gradle.api.Project;

/**
 * Registers {@code dockly { }} extension and generate/verify tasks (build.gradle SSOT).
 *
 * <p><b>Implied ProjectFacts (seeded, not re-asked):</b> {@code language=java},
 * {@code build_tool=gradle}. Remaining options come from the extension block (ADR 0010).
 * See {@code docs/plugin-facts.md}.
 */
public class DocklyPlugin implements Plugin<Project> {

    @Override
    public void apply(Project project) {
        DocklyExtension extension = project.getExtensions()
                .create("dockly", DocklyExtension.class);

        extension.getJavaVersion().convention(PluginDockerfileOptions.DEFAULT_JAVA_VERSION);
        extension.getRuntimeImage().convention(PluginDockerfileOptions.DEFAULT_RUNTIME_IMAGE);
        extension.getUseJlink().convention(true);
        extension.getUseLayeredJar().convention(true);
        extension.getNonRoot().convention(true);
        extension.getRecipe().convention(PluginDockerfileOptions.DEFAULT_RECIPE);
        extension.getOutput().convention(PluginDockerfileOptions.DEFAULT_OUTPUT);

        project.getTasks().register("docklyGenerate", GenerateDockerfileTask.class, task -> {
            task.setGroup("dockly");
            task.setDescription("Generate Dockerfile from dockly {} extension (no Python)");
            task.getJavaVersion().set(extension.getJavaVersion());
            task.getRuntimeImage().set(extension.getRuntimeImage());
            task.getUseJlink().set(extension.getUseJlink());
            task.getUseLayeredJar().set(extension.getUseLayeredJar());
            task.getNonRoot().set(extension.getNonRoot());
            task.getRecipe().set(extension.getRecipe());
            task.getOutput().set(extension.getOutput());
            task.getDockerfile().set(
                    extension.getOutput().map(name -> project.getLayout().getProjectDirectory().file(name))
            );
        });

        project.getTasks().register("docklyVerify", VerifyDockerfileTask.class, task -> {
            task.setGroup("dockly");
            task.setDescription("Verify Dockerfile matches dockly {} extension (build.gradle SSOT)");
            task.getJavaVersion().set(extension.getJavaVersion());
            task.getRuntimeImage().set(extension.getRuntimeImage());
            task.getUseJlink().set(extension.getUseJlink());
            task.getUseLayeredJar().set(extension.getUseLayeredJar());
            task.getNonRoot().set(extension.getNonRoot());
            task.getRecipe().set(extension.getRecipe());
            task.getOutput().set(extension.getOutput());
        });
    }
}
