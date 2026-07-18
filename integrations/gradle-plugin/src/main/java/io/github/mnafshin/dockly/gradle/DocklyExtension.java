package io.github.mnafshin.dockly.gradle;

import io.github.mnafshin.dockly.maven.PluginDockerfileOptions;
import org.gradle.api.provider.Property;

/** Extension block {@code dockly { ... }} — build.gradle SSOT. */
public abstract class DocklyExtension {

    public abstract Property<Integer> getJavaVersion();

    public abstract Property<String> getRuntimeImage();

    public abstract Property<Boolean> getUseJlink();

    public abstract Property<Boolean> getUseLayeredJar();

    public abstract Property<Boolean> getNonRoot();

    public abstract Property<String> getRecipe();

    public abstract Property<String> getOutput();

    public PluginDockerfileOptions toOptions() {
        return new PluginDockerfileOptions(
                getJavaVersion().getOrElse(PluginDockerfileOptions.DEFAULT_JAVA_VERSION),
                getRuntimeImage().getOrElse(PluginDockerfileOptions.DEFAULT_RUNTIME_IMAGE),
                getUseJlink().getOrElse(true),
                getUseLayeredJar().getOrElse(true),
                getNonRoot().getOrElse(true),
                getRecipe().getOrElse(PluginDockerfileOptions.DEFAULT_RECIPE),
                getOutput().getOrElse(PluginDockerfileOptions.DEFAULT_OUTPUT)
        );
    }
}
