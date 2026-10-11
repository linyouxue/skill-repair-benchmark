---
name: maven-dependency-management
description: Use when managing Maven dependencies, resolving dependency conflicts, configuring BOMs, or optimizing dependency trees in Java projects.
---

# Maven Dependency Management

Master Maven dependency management including dependency declaration, scope management, version resolution, BOMs, and dependency tree optimization.

## Overview

Maven's dependency management is a cornerstone of Java project build systems. It handles transitive dependencies, version conflicts, and provides mechanisms for controlling dependency resolution across multi-module projects.

## Dependency Declaration

### Basic Dependency

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
    <version>3.2.0</version>
</dependency>
```

### Dependency with Scope

```xml
<dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter</artifactId>
    <version>5.10.1</version>
    <scope>test</scope>
</dependency>
```

### Optional Dependencies

```xml
<dependency>
    <groupId>com.google.code.findbugs</groupId>
    <artifactId>jsr305</artifactId>
    <version>3.0.2</version>
    <optional>true</optional>
</dependency>
```

## Dependency Scopes

### Available Scopes

| Scope | Compile CP | Test CP | Runtime CP | Transitive |
|-------|-----------|---------|------------|------------|
| compile | Yes | Yes | Yes | Yes |
| provided | Yes | Yes | No | No |
| runtime | No | Yes | Yes | Yes |
| test | No | Yes | No | No |
| system | Yes | Yes | No | No |
| import | N/A | N/A | N/A | N/A |

### Scope Examples

```xml
<!-- Compile scope (default) - available everywhere -->
<dependency>
    <groupId>org.apache.commons</groupId>
    <artifactId>commons-lang3</artifactId>
    <version>3.14.0</version>
</dependency>

<!-- Provided - available at compile, not packaged -->
<dependency>
    <groupId>jakarta.servlet</groupId>
    <artifactId>jakarta.servlet-api</artifactId>
    <version>6.0.0</version>
    <scope>provided</scope>
</dependency>

<!-- Runtime - only needed at runtime -->
<dependency>
    <groupId>org.postgresql</groupId>
    <artifactId>postgresql</artifactId>
    <version>42.7.1</version>
    <scope>runtime</scope>
</dependency>

<!-- Test - only for testing -->
<dependency>
    <groupId>org.mockito</groupId>
    <artifactId>mockito-core</artifactId>
    <version>5.8.0</version>
    <scope>test</scope>
</dependency>
```

## Version Management

### Property-Based Versions

```xml
<properties>
    <spring-boot.version>3.2.0</spring-boot.version>
    <junit.version>5.10.1</junit.version>
    <jackson.version>2.16.0</jackson.version>
</properties>

<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
        <version>${spring-boot.version}</version>
    </dependency>
</dependencies>
```

### Version Ranges

```xml
<!-- Exact version -->
<version>1.0.0</version>

<!-- Greater than or equal -->
<version>[1.0.0,)</version>

<!-- Less than -->
<version>(,1.0.0)</version>

<!-- Range inclusive -->
<version>[1.0.0,2.0.0]</version>

<!-- Range exclusive -->
<version>(1.0.0,2.0.0)</version>
```

### Latest Version (Not Recommended)

```xml
<!-- Avoid in production -->
<version>LATEST</version>
<version>RELEASE</version>
```

## Dependency Management Section

### Centralizing Versions

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-dependencies</artifactId>
            <version>3.2.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
        <dependency>
            <groupId>com.fasterxml.jackson</groupId>
            <artifactId>jackson-bom</artifactId>
            <version>2.16.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>

<!-- No version needed when declared in dependencyManagement -->
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
    </dependency>
</dependencies>
```

### BOM (Bill of Materials) Import

```xml
<dependencyManagement>
    <dependencies>
        <!-- Spring Boot BOM -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-dependencies</artifactId>
            <version>3.2.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>

        <!-- AWS SDK BOM -->
        <dependency>
            <groupId>software.amazon.awssdk</groupId>
            <artifactId>bom</artifactId>
            <version>2.23.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>

        <!-- JUnit BOM -->
        <dependency>
            <groupId>org.junit</groupId>
            <artifactId>junit-bom</artifactId>
            <version>5.10.1</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

## Exclusions

### Excluding Transitive Dependencies

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
    <exclusions>
        <exclusion>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-tomcat</artifactId>
        </exclusion>
    </exclusions>
</dependency>

<!-- Add alternative -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-jetty</artifactId>
</dependency>
```

### Excluding Logging Frameworks

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter</artifactId>
    <exclusions>
        <exclusion>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-logging</artifactId>
        </exclusion>
    </exclusions>
</dependency>

<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-log4j2</artifactId>
</dependency>
```

## Dependency Analysis

### View Dependency Tree

```bash
# Full dependency tree
mvn dependency:tree

# Filter by artifact
mvn dependency:tree -Dincludes=org.slf4j

# Output to file
mvn dependency:tree -DoutputFile=deps.txt

# Verbose output showing conflict resolution
mvn dependency:tree -Dverbose
```

### Analyze Dependencies

```bash
# Find unused declared and used undeclared dependencies
mvn dependency:analyze

# Show only problems
mvn dependency:analyze-only

# Include test scope
mvn dependency:analyze -DignoreNonCompile=false
```

### List Dependencies

```bash
# List all dependencies
mvn dependency:list

# List with scope
mvn dependency:list -DincludeScope=runtime
```

## Conflict Resolution



## Concrete Remediation Patterns (What to Change)

Use these patterns once you’ve identified the conflicting artifacts/versions from `dependency:tree -Dverbose` and the effective POM.

### Pin/Align versions with `dependencyManagement`

Prefer managing versions in a parent/root POM so every module resolves the same version:

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>com.google.guava</groupId>
      <artifactId>guava</artifactId>
      <version>32.1.3-jre</version>
    </dependency>
  </dependencies>
</dependencyManagement>
```

Use this when you see multiple versions of the same artifact or Enforcer failures (`dependencyConvergence`, `requireUpperBoundDeps`).

### Align ecosystems via BOM imports

If a project depends on a family of artifacts (e.g., Jackson, Netty, gRPC), import the official BOM and remove individual versions:

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>com.fasterxml.jackson</groupId>
      <artifactId>jackson-bom</artifactId>
      <version>2.16.0</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

### Exclude unwanted transitive dependencies (surgical)

Use exclusions when a transitive dependency drags in an incompatible version or a duplicate implementation:

```xml
<dependency>
  <groupId>io.grpc</groupId>
  <artifactId>grpc-netty</artifactId>
  <exclusions>
    <exclusion>
      <groupId>com.google.guava</groupId>
      <artifactId>guava</artifactId>
    </exclusion>
  </exclusions>
</dependency>
```

Then add the desired version explicitly (or via `dependencyManagement`).

### Fix scope/optional misuse

Common repairs:
- `provided` only when the runtime/container supplies it (e.g., servlet API)
- `runtime` when only needed at runtime (JDBC drivers)
- avoid marking required compile-time dependencies as `<optional>true</optional>` in libraries (consumers won’t get them transitively)

Symptoms of wrong scope/optional:
- compiles locally but fails in downstream modules
- tests pass but packaging/runtime fails

### Annotation processor alignment (common in google/auto)

Annotation processors should be available to the compiler, but typically should not leak into runtime.

If using `maven-compiler-plugin`, configure processors explicitly and keep processor artifacts off the runtime classpath:

```xml
<plugin>
  <artifactId>maven-compiler-plugin</artifactId>
  <configuration>
    <annotationProcessorPaths>
      <path>
        <groupId>com.google.auto.value</groupId>
        <artifactId>auto-value</artifactId>
        <version>REPLACE_ME</version>
      </path>
    </annotationProcessorPaths>
  </configuration>
</plugin>
```

If you see errors like missing generated types, duplicate processors, or processor NoSuchMethodError, check:
- processor and its dependencies (e.g., Guava/Javac-related) are on a compatible set of versions
- only one processor version is present across modules (pin in `dependencyManagement`)

### Maven's Default Strategy

Maven uses "nearest definition wins" for version conflicts:

```
A -> B -> C 1.0
A -> C 2.0
```

Result: C 2.0 is used (nearest to root)

### Forcing Versions

```xml
<dependencyManagement>
    <dependencies>
        <!-- Force specific version across all modules -->
        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-api</artifactId>
            <version>2.0.9</version>
        </dependency>
    </dependencies>
</dependencyManagement>
```

### Enforcer Plugin for Version Control

```xml
<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-enforcer-plugin</artifactId>
            <version>3.4.1</version>
            <executions>
                <execution>
                    <id>enforce</id>
                    <goals>
                        <goal>enforce</goal>
                    </goals>
                    <configuration>
                        <rules>
                            <dependencyConvergence/>
                            <requireUpperBoundDeps/>
                            <banDuplicatePomDependencyVersions/>
                        </rules>
                    </configuration>
                </execution>
            </executions>
        </plugin>
    </plugins>
</build>
```

## Multi-Module Projects

### Parent POM Dependency Management

```xml
<!-- parent/pom.xml -->
<project>
    <groupId>com.example</groupId>
    <artifactId>parent</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>com.example</groupId>
                <artifactId>common</artifactId>
                <version>${project.version}</version>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>

<!-- module/pom.xml -->
<project>
    <parent>
        <groupId>com.example</groupId>
        <artifactId>parent</artifactId>
        <version>1.0.0</version>
    </parent>

    <artifactId>module</artifactId>

    <dependencies>
        <!-- Version inherited from parent -->
        <dependency>
            <groupId>com.example</groupId>
            <artifactId>common</artifactId>
        </dependency>
    </dependencies>
</project>
```

## Repository Configuration

### Central Repository

```xml
<repositories>
    <repository>
        <id>central</id>
        <url>https://repo.maven.apache.org/maven2</url>
    </repository>
</repositories>
```

### Private Repository

```xml
<repositories>
    <repository>
        <id>company-repo</id>
        <url>https://nexus.company.com/repository/maven-public</url>
        <releases>
            <enabled>true</enabled>
        </releases>
        <snapshots>
            <enabled>true</enabled>
        </snapshots>
    </repository>
</repositories>
```

### Repository in Settings.xml

```xml
<!-- ~/.m2/settings.xml -->
<settings>
    <servers>
        <server>
            <id>company-repo</id>
            <username>${env.REPO_USER}</username>
            <password>${env.REPO_PASS}</password>
        </server>
    </servers>
</settings>
```

## Best Practices

1. **Use dependencyManagement** - Centralize versions in parent POMs
2. **Import BOMs** - Use well-maintained BOMs for framework dependencies
3. **Avoid Version Ranges** - Pin exact versions for reproducibility
4. **Regular Updates** - Keep dependencies current for security
5. **Minimize Scopes** - Use appropriate scopes to reduce package size
6. **Exclude Unused** - Remove unused transitive dependencies
7. **Document Exclusions** - Comment why exclusions are needed
8. **Run dependency:analyze** - Regularly check for issues
9. **Use Enforcer Plugin** - Ensure dependency convergence
10. **Lock Versions** - Use versions-maven-plugin for updates

## Common Pitfalls

1. **Version Conflicts** - Transitive dependency version mismatches
2. **Missing Exclusions** - Duplicate classes from different artifacts
3. **Wrong Scope** - Compile vs runtime vs provided confusion
4. **Outdated Dependencies** - Security vulnerabilities in old versions
5. **Circular Dependencies** - Module A depends on B depends on A
6. **Snapshot in Production** - Using SNAPSHOT versions in releases
7. **System Scope** - Hardcoded paths break portability
8. **Optional Misuse** - Marking required dependencies as optional

## Troubleshooting



## Build-Failure Triage (Repair Workflow)

When a Maven build fails (especially in CI and/or multi-module repos), triage in this order to identify *which module*, *which classpath*, and *which resolved versions* are actually in use.

### 1) Re-run the failing build with full diagnostics

```bash
# Show stack traces
mvn -e test

# Full debug logs (very noisy, but shows repository resolution and classpath setup)
mvn -X test

# Common CI parity flags
mvn -U -DskipTests=false test
```

What to look for:
- The *first* compilation error (later errors are often cascading)
- "omitted for conflict" / "version managed from" lines
- Repositories used, authentication failures, or offline mirrors in `settings.xml`

### 2) Inspect the resolved dependency graph (per module)

```bash
# Verbose tree shows conflict mediation and why a version won
mvn -pl :<artifactId> -am dependency:tree -Dverbose

# Narrow to a suspect group/artifact
mvn -pl :<artifactId> -am dependency:tree -Dverbose -Dincludes=com.google.*
```

If the failure is in a multi-module build, always run `dependency:tree` on the *module that fails*, not only the root.

### 3) Reconstruct the actual classpath Maven uses

```bash
# Useful for "class not found" / "method not found" / duplicate class issues
mvn -pl :<artifactId> -am dependency:build-classpath -DincludeScope=compile -Dmdep.outputFile=cp.txt
```

Compare this output between local and CI if the issue is reproducible only in one environment.

### 4) Compare effective configuration (what Maven really sees)

```bash
# Shows inherited dependencyManagement, pluginManagement, profiles, properties, and activated defaults
mvn -pl :<artifactId> -am help:effective-pom -Doutput=effective-pom.xml
```

This is the fastest way to confirm:
- a BOM import is actually applied
- versions are coming from `dependencyManagement` vs direct declarations
- profiles are changing dependencies/plugins in CI

### 5) Common CI-vs-local differences to check

- JDK version and toolchain (CI may use a different `JAVA_HOME`)
- Activated profiles (`-P...`) and profile activation by property/OS/JDK
- Remote repository access (mirrors, credentials in `~/.m2/settings.xml`)
- Snapshot updates (`-U`) and stale local cache vs clean CI cache
- Reactor order and module selection (`-pl`, `-am`) masking missing inter-module deps locally

### Debug Dependency Resolution

```bash
# Re-run Maven with stack traces / debug logs (preferred for build failures)
mvn -e test
mvn -X test

# Inspect the dependency graph and conflict mediation
mvn dependency:tree -Dverbose

# Build the exact classpath Maven uses (helpful for CNFE/NoSuchMethodError)
mvn dependency:build-classpath -DincludeScope=compile -Dmdep.outputFile=cp.txt

# Confirm resolved versions, profiles, and inherited management
mvn help:effective-pom -Doutput=effective-pom.xml
```

### Force Re-download

```bash
# Clear local repository cache
mvn dependency:purge-local-repository

# Force update
mvn -U clean install
```

### Check Effective POM

```bash
# See resolved dependency versions
mvn help:effective-pom
```

## When to Use This Skill

- Adding new dependencies to a project
- Resolving version conflicts
- Setting up multi-module project dependencies
- Configuring BOM imports
- Optimizing dependency trees
- Troubleshooting classpath issues
- Upgrading dependency versions
- Excluding problematic transitive dependencies
