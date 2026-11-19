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

### Excluding JDK-internal / tools.jar Dependencies (com.sun:tools)

Some older libraries (often compilation or annotation-processing utilities used in tests) declare a `system`-scoped dependency on `com.sun:tools` that points at `${java.home}/../lib/tools.jar`.

- This works on JDK 8 and earlier.
- JDK 9+ no longer ships `tools.jar`, so dependency resolution can fail with errors mentioning `com.sun:tools` and `tools.jar`.

**How to find the source**

```bash
# Identify which dependency brings in com.sun:tools
mvn -DskipTests dependency:tree -Dverbose -Dincludes=com.sun:tools
```

Also check profiles/effective POM if a profile unexpectedly activates a tools.jar dependency:

```bash
mvn help:active-profiles
mvn help:effective-pom
```

**Common fixes (choose the smallest that preserves intent)**

1) **Upgrade** the introducing dependency to a version that supports modern JDKs.

2) **Exclude** the transitive `com.sun:tools` dependency:

```xml
<dependency>
    <groupId>com.example</groupId>
    <artifactId>some-dependency</artifactId>
    <version>${some-dependency.version}</version>
    <exclusions>
        <exclusion>
            <groupId>com.sun</groupId>
            <artifactId>tools</artifactId>
        </exclusion>
    </exclusions>
</dependency>
```

3) **Use Maven Toolchains** to build with an older JDK when the project truly requires JDK 8’s `tools.jar` (see the *maven-plugin-configuration* skill).

Avoid adding new `system`-scoped dependencies that hardcode local JDK paths; they are non-portable and commonly break CI.

### Missing `javax.annotation` (JSR-250) types on JDK 9+

Another common “old project on a modern JDK” failure is missing `javax.annotation.*` classes that used to be available via Java EE modules in older JDK distributions.

**Typical symptoms** (during compile or tests):

- `package javax.annotation does not exist`
- `cannot find symbol: class Generated`
- `NoClassDefFoundError: javax/annotation/Generated`

**Why it happens**

- JDK 9+ no longer bundles many Java EE / JSR-250 types. If source code (or generated source code) imports `javax.annotation.*`, you must supply it as a dependency.

**Common fixes (choose the smallest that preserves intent)**

1) **Add an explicit dependency** on the JSR-250 annotations artifact.

```xml
<dependency>
  <groupId>javax.annotation</groupId>
  <artifactId>javax.annotation-api</artifactId>
  <version>1.3.2</version>
</dependency>
```

- Use `compile` scope if your published classes reference these annotations and downstream consumers need them to compile.
- Use `provided` if it’s only needed to compile your sources/tests (and you don’t want to ship it transitively).

2) **Prefer JDK-provided alternatives** when feasible.

- For generated code, consider `javax.annotation.processing.Generated` (available in modern JDKs) to avoid an external dependency.

After applying a fix, re-run the original failing Maven command to ensure you didn’t just move the failure to the next module/phase.

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

### Debug Dependency Resolution

```bash
# Enable debug output
mvn dependency:tree -X

# Show conflict resolution
mvn dependency:tree -Dverbose=true
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
