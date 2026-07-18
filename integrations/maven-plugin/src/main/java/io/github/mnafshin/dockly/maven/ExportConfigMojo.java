package io.github.mnafshin.dockly.maven;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import org.apache.maven.plugin.AbstractMojo;
import org.apache.maven.plugin.MojoExecutionException;
import org.apache.maven.plugin.MojoFailureException;
import org.apache.maven.plugins.annotations.Mojo;
import org.apache.maven.plugins.annotations.Parameter;
import org.apache.maven.project.MavenProject;

/**
 * Optional bridge: write {@code .dockly.toml} from plugin configuration (POM → toml only).
 */
@Mojo(name = "export-config", requiresProject = true, threadSafe = true)
public class ExportConfigMojo extends AbstractMojo {

    @Parameter(defaultValue = "${project}", readonly = true, required = true)
    private MavenProject project;

    @Parameter(property = "dockly.javaVersion", defaultValue = "17")
    private int javaVersion;

    @Parameter(property = "dockly.runtimeImage", defaultValue = "distroless")
    private String runtimeImage;

    @Parameter(property = "dockly.useJlink", defaultValue = "true")
    private boolean useJlink;

    @Parameter(property = "dockly.useLayeredJar", defaultValue = "true")
    private boolean useLayeredJar;

    @Parameter(property = "dockly.nonRoot", defaultValue = "true")
    private boolean nonRoot;

    @Parameter(property = "dockly.recipe", defaultValue = "jvm-balanced")
    private String recipe;

    @Parameter(property = "dockly.output", defaultValue = "Dockerfile.generated")
    private String output;

    @Parameter(property = "dockly.configFile", defaultValue = ".dockly.toml")
    private String configFile;

    @Parameter(property = "dockly.force", defaultValue = "false")
    private boolean force;

    @Parameter(property = "dockly.skip", defaultValue = "false")
    private boolean skip;

    @Override
    public void execute() throws MojoExecutionException, MojoFailureException {
        if (skip) {
            getLog().info("dockly:export-config skipped");
            return;
        }

        PluginDockerfileOptions options;
        try {
            options = new PluginDockerfileOptions(
                    javaVersion, runtimeImage, useJlink, useLayeredJar, nonRoot, recipe, output
            );
        } catch (IllegalArgumentException ex) {
            throw new MojoFailureException(ex.getMessage(), ex);
        }

        File destination = new File(project.getBasedir(), configFile);
        if (destination.exists() && !force) {
            throw new MojoFailureException(
                    "Config already exists: " + destination + " — re-run with -Ddockly.force=true to overwrite"
            );
        }

        try {
            Files.writeString(destination.toPath(), TomlConfigExporter.render(options), StandardCharsets.UTF_8);
        } catch (IOException ex) {
            throw new MojoExecutionException("Failed to write " + destination + ": " + ex.getMessage(), ex);
        }
        getLog().info("Wrote " + destination.getAbsolutePath() + " (one-way export from POM SSOT)");
        getLog().info("Plugin configuration remains the builder SSOT; toml is for Python CLI adoption.");
    }
}
