package io.github.mnafshin.dockly.gradle;

import io.github.mnafshin.dockly.maven.DockerfileDriftChecker;
import io.github.mnafshin.dockly.maven.DockerfileRenderer;
import io.github.mnafshin.dockly.maven.PluginDockerfileOptions;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import javax.inject.Inject;
import org.gradle.api.DefaultTask;
import org.gradle.api.GradleException;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.file.ProjectLayout;
import org.gradle.api.provider.Property;
import org.gradle.api.tasks.Input;
import org.gradle.api.tasks.TaskAction;

/** Fails when the Dockerfile drifts from the {@code dockly} extension (build.gradle SSOT). */
public abstract class VerifyDockerfileTask extends DefaultTask {

    @Inject
    public VerifyDockerfileTask(ProjectLayout layout) {
        getProjectDirectory().convention(layout.getProjectDirectory());
    }

    @Input
    public abstract Property<Integer> getJavaVersion();

    @Input
    public abstract Property<String> getRuntimeImage();

    @Input
    public abstract Property<Boolean> getUseJlink();

    @Input
    public abstract Property<Boolean> getUseLayeredJar();

    @Input
    public abstract Property<Boolean> getNonRoot();

    @Input
    public abstract Property<String> getRecipe();

    @Input
    public abstract Property<String> getOutput();

    public abstract DirectoryProperty getProjectDirectory();

    @TaskAction
    public void verify() throws IOException {
        PluginDockerfileOptions options = new PluginDockerfileOptions(
                getJavaVersion().get(),
                getRuntimeImage().get(),
                getUseJlink().get(),
                getUseLayeredJar().get(),
                getNonRoot().get(),
                getRecipe().get(),
                getOutput().get()
        );
        Path dockerfile = getProjectDirectory().get().getAsFile().toPath().resolve(options.output());
        if (!Files.isRegularFile(dockerfile)) {
            throw new GradleException("Missing " + dockerfile + " — run docklyGenerate first");
        }
        String actual = Files.readString(dockerfile, StandardCharsets.UTF_8);
        List<String> drift = DockerfileDriftChecker.findDrift(actual, options);
        String expected = DockerfileRenderer.render(options);
        if (!DockerfileDriftChecker.normalize(actual).equals(DockerfileDriftChecker.normalize(expected))
                || !drift.isEmpty()) {
            throw new GradleException(
                    "Dockerfile drift vs dockly {} extension (build.gradle SSOT). "
                            + "Re-run docklyGenerate. Details: "
                            + drift
            );
        }
        getLogger().lifecycle("docklyVerify OK — matches build.gradle extension");
    }
}
