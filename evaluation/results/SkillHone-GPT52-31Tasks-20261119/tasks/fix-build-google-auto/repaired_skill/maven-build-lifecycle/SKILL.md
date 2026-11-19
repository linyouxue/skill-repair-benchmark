---
name: maven-build-lifecycle
description: Use when working with Maven build phases, goals, profiles, or customizing the build process for Java projects.
---

# Maven Build Lifecycle

Master Maven's build lifecycle including phases, goals, profiles, and build customization for efficient Java project builds.

## Overview

Maven's build lifecycle is a well-defined sequence of phases that execute in order. Understanding the lifecycle is essential for effective build configuration and optimization.

## Build-fix Tasks With Required Artifacts (notes + patch diffs)

Some build-fix prompts are **procedural** and require you to produce specific on-disk artifacts in addition to fixing the build, commonly:

- a short diagnosis/plan file (e.g. `.../failed_reasons.txt`),
- one or more unified diff files (e.g. `patch_1.diff`, `patch_2.diff`), and
- a final repository state where the patch is **applied** and the build is green.

When the prompt names **absolute paths**, treat them as requirements and use them verbatim.

### Compliance checklist (do not end the run early)

Before you finish, confirm all of the following are true:

1) You have located the **exact repository root** referenced by the prompt.
2) You reproduced the failure (or at least ran the same Maven goal) and wrote a concise diagnosis + plan to the required notes file.
3) You implemented the fix in the working tree.
4) You wrote at least one `patch_{i}.diff` **at the exact path/name required by the prompt** and confirmed it is non-empty.
5) You sanity-checked the patch applies cleanly (`git apply --check ...` or `patch --dry-run ...`).
6) The repository ends in the **fixed state** and the Maven build/test command succeeds.

### Minimal command pattern

Use a small, repeatable loop (adjust goals/flags to match the prompt/CI):

```bash
# 0) Discover the repo path if it contains placeholders
ls -la /path/with/placeholders
ls -la /path/with/placeholders/<repo>

# 1) Reproduce failure with useful output
mvn -B -U test -e   # or: mvn -B -U verify -e

# 2) Write diagnosis/plan to the required notes path
# (Use a heredoc or printf; keep it short and actionable.)

# 3) Edit files to fix the build

# 4) Emit unified diff patch file(s) at the required path(s)
git diff --no-color > /exact/required/path/patch_1.diff

# 5) Verify patch is present and well-formed
test -s /exact/required/path/patch_1.diff
git apply --check /exact/required/path/patch_1.diff

# 6) Re-run build to confirm green
mvn -B -U test -e
```

If the prompt requires you to explicitly “apply your diff files”, a reliable approach is:

- generate `patch_1.diff` from your in-place edits,
- `git restore -- .` (or equivalent) to return to the original state, then
- `git apply patch_1.diff` to re-apply the same changes.

This avoids the common failure mode of producing a patch but leaving the working tree unfixed (or vice versa).

## Default Lifecycle Phases

### Complete Phase Order

```
1.  validate      - Validate project structure
2.  initialize    - Initialize build state
3.  generate-sources
4.  process-sources
5.  generate-resources
6.  process-resources - Copy resources to output
7.  compile       - Compile source code
8.  process-classes
9.  generate-test-sources
10. process-test-sources
11. generate-test-resources
12. process-test-resources
13. test-compile  - Compile test sources
14. process-test-classes
15. test          - Run unit tests
16. prepare-package
17. package       - Create JAR/WAR
18. pre-integration-test
19. integration-test - Run integration tests
20. post-integration-test
21. verify        - Run verification checks
22. install       - Install to local repo
23. deploy        - Deploy to remote repo
```

### Common Phase Commands

```bash
# Compile only
mvn compile

# Compile and run tests
mvn test

# Create package
mvn package

# Install to local repository
mvn install

# Deploy to remote repository
mvn deploy

# Clean and build
mvn clean install

# Skip tests
mvn install -DskipTests

# Skip test compilation and execution
mvn install -Dmaven.test.skip=true
```

## Clean Lifecycle

```
1. pre-clean
2. clean         - Delete target directory
3. post-clean
```

```bash
# Clean build artifacts
mvn clean

# Clean specific directory
mvn clean -DbuildDirectory=out
```

## Site Lifecycle

```
1. pre-site
2. site          - Generate documentation
3. post-site
4. site-deploy   - Deploy documentation
```

```bash
# Generate site
mvn site

# Generate and deploy site
mvn site-deploy
```

## Goals vs Phases

### Executing Phases

```bash
# Execute phase (runs all previous phases)
mvn package
```

### Executing Goals

```bash
# Execute specific goal
mvn compiler:compile
mvn surefire:test
mvn jar:jar

# Multiple goals
mvn dependency:tree compiler:compile
```

### Phase-to-Goal Bindings

```xml
<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-compiler-plugin</artifactId>
            <version>3.12.1</version>
            <executions>
                <execution>
                    <id>compile-sources</id>
                    <phase>compile</phase>
                    <goals>
                        <goal>compile</goal>
                    </goals>
                </execution>
            </executions>
        </plugin>
    </plugins>
</build>
```

## Build Profiles

### Profile Definition

```xml
<profiles>
    <profile>
        <id>development</id>
        <activation>
            <activeByDefault>true</activeByDefault>
        </activation>
        <properties>
            <env>dev</env>
            <skip.integration.tests>true</skip.integration.tests>
        </properties>
    </profile>

    <profile>
        <id>production</id>
        <properties>
            <env>prod</env>
            <skip.integration.tests>false</skip.integration.tests>
        </properties>
        <build>
            <plugins>
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-compiler-plugin</artifactId>
                    <configuration>
                        <debug>false</debug>
                        <optimize>true</optimize>
                    </configuration>
                </plugin>
            </plugins>
        </build>
    </profile>
</profiles>
```

### Profile Activation

```bash
# Activate by name
mvn install -Pproduction

# Multiple profiles
mvn install -Pproduction,ci

# Deactivate profile
mvn install -P!development
```

### Activation Triggers

```xml
<profile>
    <id>jdk17</id>
    <activation>
        <!-- Activate by JDK version -->
        <jdk>17</jdk>
    </activation>
</profile>

<profile>
    <id>windows</id>
    <activation>
        <!-- Activate by OS -->
        <os>
            <family>windows</family>
        </os>
    </activation>
</profile>

<profile>
    <id>ci</id>
    <activation>
        <!-- Activate by environment variable -->
        <property>
            <name>env.CI</name>
            <value>true</value>
        </property>
    </activation>
</profile>

<profile>
    <id>with-config</id>
    <activation>
        <!-- Activate by file existence -->
        <file>
            <exists>src/main/config/app.properties</exists>
        </file>
    </activation>
</profile>
```

## Resource Filtering

### Enable Filtering

```xml
<build>
    <resources>
        <resource>
            <directory>src/main/resources</directory>
            <filtering>true</filtering>
            <includes>
                <include>**/*.properties</include>
                <include>**/*.xml</include>
            </includes>
        </resource>
        <resource>
            <directory>src/main/resources</directory>
            <filtering>false</filtering>
            <excludes>
                <exclude>**/*.properties</exclude>
                <exclude>**/*.xml</exclude>
            </excludes>
        </resource>
    </resources>
</build>
```

### Property Substitution

```properties
# application.properties
app.name=${project.name}
app.version=${project.version}
app.environment=${env}
build.timestamp=${maven.build.timestamp}
```

## Build Customization

### Source and Target Configuration

```xml
<properties>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <maven.compiler.release>17</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
</properties>
```

### Custom Source Directories

```xml
<build>
    <sourceDirectory>src/main/java</sourceDirectory>
    <testSourceDirectory>src/test/java</testSourceDirectory>
    <resources>
        <resource>
            <directory>src/main/resources</directory>
        </resource>
    </resources>
    <testResources>
        <testResource>
            <directory>src/test/resources</directory>
        </testResource>
    </testResources>
</build>
```

### Final Name and Output

```xml
<build>
    <finalName>${project.artifactId}-${project.version}</finalName>
    <directory>target</directory>
    <outputDirectory>target/classes</outputDirectory>
    <testOutputDirectory>target/test-classes</testOutputDirectory>
</build>
```

## Multi-Module Builds

### Reactor Options

```bash
# Build all modules
mvn install

# Build specific module and dependencies
mvn install -pl module-name -am

# Build dependents of a module
mvn install -pl module-name -amd

# Resume from specific module
mvn install -rf :module-name

# Build in parallel
mvn install -T 4
mvn install -T 1C  # 1 thread per CPU core
```

### Module Order Control

```xml
<!-- parent/pom.xml -->
<modules>
    <module>common</module>
    <module>api</module>
    <module>service</module>
    <module>web</module>
</modules>
```

## Test Configuration

### Surefire Plugin (Unit Tests)

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-surefire-plugin</artifactId>
    <version>3.2.3</version>
    <configuration>
        <includes>
            <include>**/*Test.java</include>
            <include>**/*Tests.java</include>
        </includes>
        <excludes>
            <exclude>**/*IntegrationTest.java</exclude>
        </excludes>
        <parallel>methods</parallel>
        <threadCount>4</threadCount>
        <forkCount>1</forkCount>
        <reuseForks>true</reuseForks>
    </configuration>
</plugin>
```

### Failsafe Plugin (Integration Tests)

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-failsafe-plugin</artifactId>
    <version>3.2.3</version>
    <executions>
        <execution>
            <goals>
                <goal>integration-test</goal>
                <goal>verify</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <includes>
            <include>**/*IT.java</include>
            <include>**/*IntegrationTest.java</include>
        </includes>
    </configuration>
</plugin>
```

## Build Optimization

### Incremental Builds

```bash
# Skip unchanged modules
mvn install -amd

# Use build cache (requires Maven Daemon)
mvnd install
```

### Parallel Builds

```xml
<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-compiler-plugin</artifactId>
            <configuration>
                <fork>true</fork>
                <compilerArgs>
                    <arg>-J-Xmx512m</arg>
                </compilerArgs>
            </configuration>
        </plugin>
    </plugins>
</build>
```

### Build Cache

```bash
# Enable build cache (Maven 4+)
mvn install -Dmaven.build.cache.enabled=true
```

## Fast Build Triage Workflow (CI-style)

When you need to quickly reproduce and localize a failing Maven build (especially in multi-module projects), use a small set of commands to:

1) reproduce the same goal/flags as CI,
2) reduce noise (resume from failure, build only what’s needed), and
3) isolate whether failure is in dependency resolution, compilation, tests, or a plugin.

### 1) Reproduce with CI flags

- Prefer the exact Maven command from CI configuration.
- Add `-e` (errors) for stacktraces and optionally `-X` (debug) only when needed.

```bash
mvn -B -U verify -DskipTests=false -e
```

### 2) Fail at end vs fail fast

- `--fail-at-end` can show all failing modules in a reactor build.
- `-ff`/`--fail-fast` stops at the first failure (faster iteration).

```bash
mvn -B verify --fail-at-end
mvn -B verify -ff
```

### 3) Narrow to a module (reactor options)

```bash
# Build a single module and its dependencies
mvn -pl :module-artifactId -am test

# Build only modules that depend on a module
mvn -pl :module-artifactId -amd test

# Resume from the failed module shown in output
mvn -rf :module-artifactId test
```

### 4) Distinguish dependency resolution failures from build/test failures

If the build fails before compilation, inspect the dependency graph:

```bash
mvn -DskipTests dependency:tree -Dverbose
mvn -DskipTests dependency:tree -Dincludes=groupId:artifactId
```

If compilation fails due to Java level or toolchain issues, check the effective compiler configuration:

```bash
mvn help:effective-pom
```

### 5) Control tests during iteration

```bash
# Run only unit tests
mvn -Dtest=SomeTest test

# Skip tests but still compile them
mvn -DskipTests verify

# Skip test compilation + execution (use sparingly)
mvn -Dmaven.test.skip=true verify
```

### 6) If the task requires “notes → patch.diff → apply” (diff-first workflow)

Some build-fix tasks require you to:

1) write a short diagnosis/plan to a specific file (often outside the repo),
2) write one or more `patch_{i}.diff` files in **git-style unified diff** format at an **exact** path/name, and
3) apply those diffs so the working tree ends in the fixed state.

A reliable pattern is:

```bash
# 0) Be in the repo root you are fixing (the prompt typically gives the path).
cd /path/to/repo/root

# 1) Set the *exact* patch path required by the prompt.
#    If the prompt gives an absolute path (e.g. /.../patch_1.diff), use it verbatim.
REPO_ROOT="$(pwd)"
PATCH_1="${REPO_ROOT}/patch_1.diff"   # adjust to match the prompt (patch_2.diff, etc.)

# If the prompt expects a patch in a different directory than the repo root,
# set PATCH_1 to that exact absolute path instead.

# 2) After editing files in-place, write a unified diff patch.
#    (If this produces an empty file, you likely forgot to edit or are in the wrong repo.)
git diff --no-color > "$PATCH_1"

# 3) Verify the patch file exists *where the prompt expects* and is non-empty.
ls -la "$PATCH_1"
test -s "$PATCH_1"

# 4) Sanity-check that the patch is well-formed and applies cleanly.
git apply --check "$PATCH_1"

# 5) IMPORTANT: ensure the repository ends in the fixed state.
#    - If you already edited files, you may already be done.
#    - If you must demonstrate “apply patch” explicitly, reset then apply:
# git restore -- .        # or: git checkout -- .
# git apply "$PATCH_1"
```

Tips:

- Don’t “clean up” by restoring files and then forget to re-apply; you’ll lose the fix and the build will still fail.
- Prefer variables for long paths to avoid typos; re-check with `pwd` and `ls` before moving on.
- If command output is truncated, redirect it to a log and inspect the tail:

  ```bash
  mvn -B -U verify -e > mvn.log 2>&1
  tail -n 200 mvn.log
  ```

- Re-run the original failing Maven command after applying the patch to confirm the build is actually green.

## Debugging Builds

### Verbose Output

```bash
# Debug mode
mvn install -X

# Error stacktrace
mvn install -e

# Quiet mode
mvn install -q
```

### Effective POM

```bash
# View resolved POM
mvn help:effective-pom

# View effective settings
mvn help:effective-settings

# Active profiles
mvn help:active-profiles
```

### Dependency Analysis

```bash
# Check plugin versions
mvn versions:display-plugin-updates

# Check dependency versions
mvn versions:display-dependency-updates
```

## Best Practices

1. **Use Clean Builds** - Run `mvn clean` before releases
2. **Consistent Versions** - Lock plugin versions
3. **Profile Isolation** - Keep profiles focused
4. **Fail Fast** - Use `-ff` in CI for quick feedback
5. **Parallel Builds** - Use `-T` for multi-module projects
6. **Skip Wisely** - Know the difference between skip options
7. **Resource Filtering** - Enable only where needed
8. **Test Separation** - Unit tests in Surefire, integration in Failsafe
9. **Reproducible Builds** - Pin all plugin versions
10. **Document Profiles** - Comment profile purposes

## Common Pitfalls

1. **Skipping Tests** - Don't skip tests in CI
2. **SNAPSHOT in Release** - Remove snapshots before release
3. **Missing Clean** - Stale files causing issues
4. **Profile Conflicts** - Overlapping profile configurations
5. **Resource Filtering** - Accidentally filtering binaries
6. **Phase Confusion** - Running wrong phase
7. **Memory Issues** - Insufficient heap for large builds
8. **Reactor Order** - Module dependency issues

## CI/CD Integration

### GitHub Actions

```yaml
- name: Build with Maven
  run: mvn -B clean verify -Pci

- name: Release
  run: mvn -B deploy -Prelease -DskipTests
```

### Jenkins Pipeline

```groovy
stage('Build') {
    steps {
        sh 'mvn -B clean package -DskipTests'
    }
}
stage('Test') {
    steps {
        sh 'mvn -B test'
    }
}
stage('Integration Test') {
    steps {
        sh 'mvn -B verify -DskipUnitTests'
    }
}
```

## When to Use This Skill

- Setting up new Maven projects
- Customizing build phases
- Creating build profiles for environments
- Configuring test execution
- Optimizing build performance
- Debugging build failures
- Setting up CI/CD pipelines
- Multi-module project configuration
