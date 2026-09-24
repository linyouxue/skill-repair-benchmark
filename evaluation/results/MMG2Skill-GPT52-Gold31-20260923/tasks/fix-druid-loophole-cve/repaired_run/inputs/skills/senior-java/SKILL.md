---
name: senior-java
title: Senior Java Skill Package
description: Make and apply targeted git patches to a Java/Maven repo, handle Maven
  dependency-resolution build breaks (e.g., missing SNAPSHOT artifacts), and rebuild
  with the required Maven flags.
domain: engineering
subdomain: java-development
difficulty: advanced
time-saved: 60%+ on project scaffolding, 40% on security implementation
frequency: Daily for enterprise development teams
use-cases:
- Building enterprise Spring Boot applications with production-ready configuration
- Designing microservices with Spring Cloud and service discovery
- Implementing JPA/Hibernate data layers with optimized queries
- Setting up Spring Security with OAuth2 and JWT authentication
- Performance tuning JVM applications and reactive WebFlux systems
related-agents:
- cs-java-engineer
related-skills:
- senior-backend
- senior-architect
related-commands: []
orchestrated-by:
- cs-java-engineer
dependencies:
  scripts:
  - spring_project_scaffolder.py
  - dependency_analyzer.py
  - entity_generator.py
  - api_endpoint_generator.py
  - security_config_generator.py
  - performance_profiler.py
  references:
  - spring-boot-best-practices.md
  - microservices-patterns.md
  - jpa-hibernate-guide.md
  - spring-security-reference.md
  - java-performance-tuning.md
  assets: []
compatibility: 'Python 3.8+; platforms: macos, linux, windows'
tech-stack:
- Java 17/21 LTS
- Spring Boot 3.x
- Spring Framework 6.x
- Spring Cloud
- Spring Security
- Spring Data JPA
- Hibernate ORM
- Maven/Gradle
- JUnit 5
- Mockito
- Docker
- Kubernetes
examples:
- title: Spring Boot Project Scaffolding
  input: python scripts/spring_project_scaffolder.py my-service --type microservice
    --db postgresql
  output: Complete Spring Boot 3.x project with layered architecture, Docker setup,
    and CI/CD pipeline
- title: Entity Generation
  input: python scripts/entity_generator.py User --fields 'id:Long,email:String,name:String,createdAt:LocalDateTime'
  output: JPA entity with repository, service, controller, and DTO classes
stats:
  downloads: 0
  stars: 0
  rating: 0.0
  reviews: 0
version: v1.0.0
author: Claude Skills Team
contributors: []
created: 2025-12-16
updated: 2025-12-16
license: MIT
tags:
- java
- spring-boot
- spring-framework
- microservices
- jpa
- hibernate
- spring-cloud
- webflux
- enterprise
- cloud-native
- maven
- gradle
- api
- backend
featured: false
verified: true
---

## Steps
1. Work from `/root/druid` and keep changes reviewable:
   - Use `git status` and `git --no-pager diff` to confirm the exact edits to be patched.
2. When using the shell tool, **do not submit multiple separate commands in one call** unless they are explicitly chained (e.g., `cmd1 && cmd2`)—otherwise run them as separate tool calls.
3. If the Maven build fails due to an unavailable SNAPSHOT artifact (e.g., `org.apache.apache.resources:apache-jar-resource-bundle:1.5-SNAPSHOT` used by `maven-remote-resources-plugin`):
   - Locate the exact `pom.xml` entry referencing the SNAPSHOT.
   - Replace it with a released version available from Maven Central (e.g., `1.5`).
4. Create patch files under `/root/patches/` (one patch per logical change) directly from the git diff, e.g.:
   - `git --no-pager diff > /root/patches/0001-...patch`
   - Verify with `ls -l /root/patches/`.
5. Rebuild using the **exact** required command (skipping checks/tests and excluding web-console), and confirm `BUILD SUCCESS`:
   - `mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am`
6. Confirm the expected JARs exist under the relevant module `target/` directories (processing/core/server/indexing-service) after the successful build.
## Expected Result
Patch files are present in `/root/patches/`, the repository at `/root/druid/` builds successfully with the specified Maven invocation, and the rebuilt artifacts exist in the expected `target/` paths.
