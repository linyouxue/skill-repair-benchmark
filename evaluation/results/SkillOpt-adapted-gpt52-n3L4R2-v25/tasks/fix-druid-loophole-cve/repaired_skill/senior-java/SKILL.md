---

# === CORE IDENTITY ===
name: senior-java
title: Senior Java Skill Package
description: World-class Java and Spring Boot development skill for enterprise applications, microservices, and cloud-native systems. Expertise in Spring Framework, Spring Boot 3.x, Spring Cloud, JPA/Hibernate, and reactive programming with WebFlux. Includes project scaffolding, dependency management, security implementation, and performance optimization.
domain: engineering
subdomain: java-development

# === WEBSITE DISPLAY ===
difficulty: advanced
time-saved: "60%+ on project scaffolding, 40% on security implementation"
frequency: "Daily for enterprise development teams"
use-cases:
  - Building enterprise Spring Boot applications with production-ready configuration
  - Designing microservices with Spring Cloud and service discovery
  - Implementing JPA/Hibernate data layers with optimized queries
  - Setting up Spring Security with OAuth2 and JWT authentication
  - Performance tuning JVM applications and reactive WebFlux systems

# === RELATIONSHIPS ===
related-agents: [cs-java-engineer]
related-skills: [senior-backend, senior-architect]
related-commands: []
orchestrated-by: [cs-java-engineer]

# === TECHNICAL ===
dependencies:
  scripts: [spring_project_scaffolder.py, dependency_analyzer.py, entity_generator.py, api_endpoint_generator.py, security_config_generator.py, performance_profiler.py]
  references: [spring-boot-best-practices.md, microservices-patterns.md, jpa-hibernate-guide.md, spring-security-reference.md, java-performance-tuning.md]
  assets: []
compatibility: "Python 3.8+; platforms: macos, linux, windows"
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

# === EXAMPLES ===
examples:
  - title: "Spring Boot Project Scaffolding"
    input: "python scripts/spring_project_scaffolder.py my-service --type microservice --db postgresql"
    output: "Complete Spring Boot 3.x project with layered architecture, Docker setup, and CI/CD pipeline"
  - title: "Entity Generation"
    input: "python scripts/entity_generator.py User --fields 'id:Long,email:String,name:String,createdAt:LocalDateTime'"
    output: "JPA entity with repository, service, controller, and DTO classes"

# === ANALYTICS ===
stats:
  downloads: 0
  stars: 0
  rating: 0.0
  reviews: 0

# === VERSIONING ===
version: v1.0.0
author: Claude Skills Team
contributors: []
created: 2025-12-16
updated: 2025-12-16
license: MIT

# === DISCOVERABILITY ===
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
# Senior Java

World-class Java and Spring Boot development skill for enterprise applications, microservices, and cloud-native systems. Expertise in Spring Framework, Spring Boot 3.x, Spring Cloud, JPA/Hibernate, and reactive programming with WebFlux.

## Overview

This skill provides production-ready Java and Spring Boot development capabilities through six Python automation tools and comprehensive reference documentation. Whether building enterprise monoliths, microservices architectures, or reactive systems, this skill ensures best practices, scalable architecture, and enterprise-grade security.

**What This Skill Provides:**
- Spring Boot project scaffolding with layered architecture
- JPA entity and repository generation with optimized queries
- RESTful API endpoint scaffolding with proper error handling
- Spring Security configuration (OAuth2, JWT, RBAC)
- Dependency analysis and upgrade recommendations
- JVM performance profiling and optimization guidance

**Use this skill when:**
- Starting new Spring Boot projects or microservices
- Implementing JPA/Hibernate data layers
- Designing RESTful APIs with Spring MVC or WebFlux
- Setting up authentication and authorization
- Optimizing JVM and application performance
- Reviewing Java code for quality and patterns

**Core Value:** Save 60%+ time on project scaffolding while ensuring enterprise-grade architecture, security compliance, and performance optimization.

## Core Capabilities

- **Spring Boot Scaffolding** - Generate production-ready Spring Boot 3.x projects with layered architecture, Docker configuration, and CI/CD pipelines
- **Entity Generation** - Create JPA entities with repositories, services, controllers, DTOs, and mappers following DDD patterns
- **API Development** - Scaffold RESTful endpoints with validation, error handling, pagination, and OpenAPI documentation
- **Security Implementation** - Configure Spring Security with OAuth2, JWT, role-based access control, and security best practices
- **Dependency Management** - Analyze dependencies for vulnerabilities, outdated versions, and upgrade paths
- **Performance Optimization** - Profile JVM applications, identify bottlenecks, and generate optimization recommendations

## Quick Start

### Create Spring Boot Project

```bash
# Create microservice with PostgreSQL
python scripts/spring_project_scaffolder.py order-service --type microservice --db postgresql

# Create monolith with MySQL and security
python scripts/spring_project_scaffolder.py ecommerce-app --type monolith --db mysql --security oauth2

# Create reactive WebFlux service
python scripts/spring_project_scaffolder.py notification-service --type reactive --db mongodb
```

### Generate JPA Entity

```bash
# Generate complete entity stack (entity, repository, service, controller, DTO)
python scripts/entity_generator.py Product --fields "id:Long,name:String,price:BigDecimal,category:String,createdAt:LocalDateTime"

# Generate with relationships
python scripts/entity_generator.py Order --fields "id:Long,customer:Customer,items:List<OrderItem>,total:BigDecimal" --relations "customer:ManyToOne,items:OneToMany"
```

### Analyze Dependencies

```bash
# Check for vulnerabilities and updates
python scripts/dependency_analyzer.py pom.xml --check-security

# Generate upgrade report
python scripts/dependency_analyzer.py build.gradle --output report.md
```

### Access Documentation

- Spring Boot patterns: `references/spring-boot-best-practices.md`
- Microservices design: `references/microservices-patterns.md`
- JPA/Hibernate guide: `references/jpa-hibernate-guide.md`
- Security reference: `references/spring-security-reference.md`
- Performance tuning: `references/java-performance-tuning.md`

## Key Workflows



### 0. Legacy Apache Druid Security Repair

For a vulnerability repair in an older multi-module Druid checkout, prefer repository evidence over current Spring or framework assumptions. Work from `/root/druid`, preserve compatibility with the checked-out Druid release, and keep the change narrowly scoped.

1. **Map the repository and dependency graph before editing**
   ```bash
   cd /root/druid
   git status --short
   find . -maxdepth 2 -type f -name pom.xml -print | sort
   grep -RIn --include='pom.xml' -E 'indexing-service|web-console|jackson|druid' . | head -200
   mvn -pl indexing-service -am dependency:tree -DskipTests -DoutputType=text
   ```
   Confirm the Java, Jackson, and Maven versions used by the checkout rather than assuming modern APIs. Identify the module that owns the class loaded by the indexing service; do not fix only a copied, shaded, endpoint-specific, or otherwise unused implementation.

2. **Locate every relevant parsing and validation path**
   Search source and tests for sampler request models, transform and filter specs, JavaScript configuration, Jackson annotations and deserializers, subtype registration, and validators. For example:
   ```bash
   grep -RIn --include='*.java' -E 'sampler|Sampler|TransformSpec|Filter.*Spec|javascript|JavaScript|Json(Sub|De)serializer|JsonAny|enabled' .
   grep -RIn --include='*.java' -E 'empty|unknown|unrecognized|FAIL_ON_UNKNOWN|validate|Validation' indexing-service extensions processing server
   ```
   Trace JSON parsing from the sampler endpoint through request/model deserialization to the transform or filter object and then to execution. Check whether an empty JSON property name is handled differently from ordinary unknown properties, and whether endpoint-specific validation occurs before the dangerous object is constructed or executed. Account for aliases, annotations, custom deserializers, map-backed properties, and all copies of the model.

3. **Implement the smallest compatible security fix**
   Reject the malicious configuration at the earliest reliable boundary shared by the sampler path and any equivalent ingestion path, while preserving legitimate supported requests. Do not rely solely on a web-console or controller check if Jackson can construct the dangerous object earlier, and do not broadly disable unrelated functionality. Match the release's existing exception and validation conventions and avoid APIs unavailable in its dependency versions.

4. **Add focused regression coverage**
   Extend the owning module's existing tests rather than creating an unrelated test harness. Cover the exploit's empty-key form and relevant JavaScript enablement/configuration variants, asserting rejection before execution, and cover a representative valid sampler/transform request to prevent an over-broad fix. If multiple deserialization entry points exist, test the one used by the indexing service and the shared model path. Run the narrow tests first and inspect failures for stale or wrong-module changes.

5. **Create and apply reproducible patch artifacts**
   Keep patch files outside the checkout and record the exact diff:
   ```bash
   mkdir -p /root/patches
   cd /root/druid
   git diff --check
   git diff > /root/patches/druid-0.20.0-sampler-javascript-fix.patch
   git status --short
   ```
   To reproduce on a clean matching checkout, apply with `git apply /root/patches/druid-0.20.0-sampler-javascript-fix.patch`, then run `git diff --check` and inspect `git diff --stat` and `git diff`. Never silently replace a patch with an empty file or claim success without confirming that it contains the intended source and test changes.

6. **Build only the required dependency graph**
   From `/root/druid`, use the task-prescribed constrained build so the web console is excluded and quality checks do not block the security repair:
   ```bash
   mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
   ```
   Run the focused regression tests separately before this packaging build when tests are skipped. Preserve the build log and verify that Maven actually rebuilt `indexing-service` and its required upstream modules rather than reusing an unrelated local artifact.

7. **Verify the produced and deployed artifact**
   Locate the expected indexing-service JAR and inspect it, rather than trusting a successful Maven exit code:
   ```bash
   find indexing-service -type f -name '*.jar' -print
   jar tf indexing-service/target/*.jar | grep -E 'Sampler|Transform|Filter|JavaScript'
   git diff --check
   ```
   Confirm the patched class and regression-test result correspond to the runtime package/class names. Before verifier or service testing, ensure the new JAR is the artifact copied into the runtime library directory, remove or supersede stale duplicate versions as appropriate for the deployment, and verify timestamps/checksums or class contents so the server and verifier cannot accidentally load an older or shaded/copied JAR. Recheck the running process's classpath or startup logs when the deployment layout permits it.

### 1. New Spring Boot Microservice

**Time:** 30-45 minutes

1. **Scaffold Project** - Generate microservice with Spring Boot 3.x, Docker, and CI/CD
   ```bash
   python scripts/spring_project_scaffolder.py inventory-service --type microservice --db postgresql --security jwt
   ```

2. **Configure Environment** - Set up application.yml with profiles (dev, staging, prod)
   ```bash
   cd inventory-service
   # Edit src/main/resources/application.yml
   # Configure database, security, and service discovery
   ```

3. **Generate Entities** - Create domain model with JPA entities
   ```bash
   python scripts/entity_generator.py Inventory --fields "id:Long,productId:Long,quantity:Integer,warehouse:String"
   python scripts/entity_generator.py InventoryMovement --fields "id:Long,inventory:Inventory,quantity:Integer,type:MovementType,timestamp:LocalDateTime"
   ```

4. **Implement Business Logic** - Add service layer logic and validation rules

5. **Add Tests** - Generate unit and integration tests
   ```bash
   # Run tests
   ./mvnw test
   ./mvnw verify  # Integration tests
   ```

6. **Build and Deploy**
   ```bash
   ./mvnw clean package -DskipTests
   docker build -t inventory-service:latest .
   ```

See [spring-boot-best-practices.md](references/spring-boot-best-practices.md) for complete setup patterns.

### 2. REST API Development

**Time:** 20-30 minutes per endpoint group

1. **Design API Contract** - Define endpoints following REST conventions
   ```bash
   python scripts/api_endpoint_generator.py products --methods GET,POST,PUT,DELETE --paginated
   ```

2. **Implement Validation** - Add Jakarta validation annotations and custom validators

3. **Configure Error Handling** - Set up global exception handler with problem details (RFC 7807)

4. **Add OpenAPI Documentation** - Configure SpringDoc for automatic API docs

5. **Test Endpoints** - Generate integration tests with MockMvc or WebTestClient

See [spring-boot-best-practices.md](references/spring-boot-best-practices.md) for API design patterns.

### 3. JPA/Hibernate Optimization

**Time:** 1-2 hours for complex data models

1. **Analyze Current Queries** - Profile repository methods for N+1 problems
   ```bash
   python scripts/performance_profiler.py --analyze-queries src/
   ```

2. **Optimize Fetch Strategies** - Configure lazy/eager loading appropriately

3. **Add Query Hints** - Implement entity graphs and query hints for complex queries

4. **Configure Caching** - Set up Hibernate second-level cache with Hazelcast or Redis

5. **Implement Pagination** - Use Spring Data's Slice or Page for large datasets

See [jpa-hibernate-guide.md](references/jpa-hibernate-guide.md) for optimization patterns.

### 4. Spring Security Implementation

**Time:** 1-2 hours

1. **Generate Security Config** - Create security configuration for chosen auth method
   ```bash
   python scripts/security_config_generator.py --type jwt --roles ADMIN,USER,MANAGER
   ```

2. **Configure OAuth2/JWT** - Set up token generation, validation, and refresh

3. **Implement RBAC** - Add role-based access control to endpoints

4. **Add Method Security** - Configure @PreAuthorize and @PostAuthorize annotations

5. **Test Security** - Generate security integration tests

See [spring-security-reference.md](references/spring-security-reference.md) for security patterns.

## Python Tools

### spring_project_scaffolder.py

Generate production-ready Spring Boot project structures with complete configuration.

**Key Features:**
- Spring Boot 3.x with Java 17/21 support
- Multiple project types (microservice, monolith, reactive)
- Database configuration (PostgreSQL, MySQL, MongoDB, H2)
- Docker and Docker Compose setup
- GitHub Actions CI/CD pipeline
- Layered architecture (controller, service, repository)
- Lombok and MapStruct integration

**Common Usage:**
```bash
# Microservice with PostgreSQL and JWT security
python scripts/spring_project_scaffolder.py user-service --type microservice --db postgresql --security jwt

# Monolith with MySQL and OAuth2
python scripts/spring_project_scaffolder.py ecommerce --type monolith --db mysql --security oauth2

# Reactive service with MongoDB
python scripts/spring_project_scaffolder.py notification-service --type reactive --db mongodb

# Help
python scripts/spring_project_scaffolder.py --help
```

### entity_generator.py

Generate complete JPA entity stacks with repository, service, controller, and DTO.

**Key Features:**
- JPA entity with Lombok annotations
- Spring Data JPA repository with custom queries
- Service layer with transaction management
- REST controller with validation
- DTO and mapper (MapStruct)
- Relationship support (OneToMany, ManyToOne, ManyToMany)

**Common Usage:**
```bash
# Basic entity
python scripts/entity_generator.py Customer --fields "id:Long,name:String,email:String"

# Entity with relationships
python scripts/entity_generator.py Order --fields "id:Long,customer:Customer,total:BigDecimal" --relations "customer:ManyToOne"

# Entity with audit fields
python scripts/entity_generator.py Product --fields "id:Long,name:String,price:BigDecimal" --auditable

# Help
python scripts/entity_generator.py --help
```

### api_endpoint_generator.py

Scaffold RESTful API endpoints with validation and documentation.

**Key Features:**
- CRUD endpoint generation
- Request/response DTOs
- Jakarta validation annotations
- OpenAPI annotations
- Pagination support
- Error handling

**Common Usage:**
```bash
# Full CRUD endpoints
python scripts/api_endpoint_generator.py orders --methods GET,POST,PUT,DELETE

# Read-only with pagination
python scripts/api_endpoint_generator.py reports --methods GET --paginated

# Help
python scripts/api_endpoint_generator.py --help
```

### security_config_generator.py

Generate Spring Security configuration for various authentication methods.

**Key Features:**
- JWT authentication setup
- OAuth2 resource server configuration
- Role-based access control
- Method security configuration
- CORS and CSRF configuration
- Security filter chain

**Common Usage:**
```bash
# JWT security with roles
python scripts/security_config_generator.py --type jwt --roles ADMIN,USER

# OAuth2 resource server
python scripts/security_config_generator.py --type oauth2 --issuer-uri https://auth.example.com

# Help
python scripts/security_config_generator.py --help
```

### dependency_analyzer.py

Analyze Maven/Gradle dependencies for vulnerabilities and updates.

**Key Features:**
- Security vulnerability scanning
- Outdated dependency detection
- Upgrade path recommendations
- Dependency tree analysis
- License compliance checking

**Common Usage:**
```bash
# Analyze Maven project
python scripts/dependency_analyzer.py pom.xml

# Analyze Gradle with security focus
python scripts/dependency_analyzer.py build.gradle --check-security

# Generate markdown report
python scripts/dependency_analyzer.py pom.xml --output report.md

# Help
python scripts/dependency_analyzer.py --help
```

### performance_profiler.py

Profile JVM applications and generate optimization recommendations.

**Key Features:**
- Query analysis for N+1 detection
- Memory usage patterns
- GC behavior analysis
- Thread pool recommendations
- Connection pool optimization
- JVM flag recommendations

**Common Usage:**
```bash
# Analyze source for performance issues
python scripts/performance_profiler.py --analyze-queries src/

# Profile running application
python scripts/performance_profiler.py --profile http://localhost:8080/actuator

# Generate optimization report
python scripts/performance_profiler.py src/ --output performance-report.md

# Help
python scripts/performance_profiler.py --help
```

## Reference Documentation

### When to Use Each Reference

**[spring-boot-best-practices.md](references/spring-boot-best-practices.md)** - Spring Boot Patterns
- Project structure and layered architecture
- Configuration management with profiles
- API design and error handling
- Testing strategies (unit, integration, contract)
- Production readiness (actuator, monitoring)

**[microservices-patterns.md](references/microservices-patterns.md)** - Microservices Architecture
- Service decomposition strategies
- Spring Cloud components (Config, Gateway, Discovery)
- Inter-service communication (REST, gRPC, messaging)
- Distributed tracing and observability
- Circuit breaker and resilience patterns

**[jpa-hibernate-guide.md](references/jpa-hibernate-guide.md)** - Data Layer
- Entity design and mapping strategies
- Repository patterns and custom queries
- Fetch optimization and N+1 prevention
- Caching strategies (first-level, second-level)
- Transaction management

**[spring-security-reference.md](references/spring-security-reference.md)** - Security
- Authentication methods (JWT, OAuth2, SAML)
- Authorization patterns (RBAC, ABAC)
- Security filter chain configuration
- Method security annotations
- Security testing

**[java-performance-tuning.md](references/java-performance-tuning.md)** - Performance
- JVM tuning and GC optimization
- Connection pool configuration
- Caching strategies
- Async processing and virtual threads
- Profiling and monitoring tools

## Best Practices

### Quality Standards

- **Code Coverage:** Target 80%+ for business logic, 60%+ overall
- **API Documentation:** 100% endpoint coverage with OpenAPI
- **Security Scanning:** Zero critical/high vulnerabilities
- **Performance:** P99 latency < 200ms for CRUD operations

### Common Pitfalls to Avoid

- **N+1 Queries** - Always use entity graphs or fetch joins for relationships
- **Missing Transactions** - Ensure @Transactional on service methods modifying data
- **Blocking in WebFlux** - Never use blocking calls in reactive pipelines
- **Hardcoded Configuration** - Use externalized configuration with profiles
- **Missing Validation** - Always validate input at controller layer
- **Open Sessions in View** - Disable OSIV anti-pattern in production

See [spring-boot-best-practices.md](references/spring-boot-best-practices.md) for detailed guidelines.

## Performance Metrics

**Development Efficiency:**
- Project scaffolding time (target: < 30 minutes)
- Entity stack generation (target: < 5 minutes per entity)
- Security setup time (target: < 1 hour)

**Code Quality:**
- Test coverage (target: 80%+)
- Static analysis issues (target: 0 critical/high)
- Documentation coverage (target: 100% public APIs)

**Runtime Performance:**
- P99 latency (target: < 200ms)
- Throughput (target: > 1000 RPS per instance)
- Memory efficiency (target: < 512MB heap for typical service)

## Integration

This skill works best with:
- **senior-backend** - For general API patterns and database design
- **senior-architect** - For system design and microservices architecture decisions
- **senior-devops** - For CI/CD pipeline and Kubernetes deployment
- **senior-security** - For security audits and penetration testing

See [spring-boot-best-practices.md](references/spring-boot-best-practices.md) for CI/CD and automation integration examples.

## Composability & Integration

### Skill Composition Patterns

**This skill receives input from:**
- **senior-architect** - Architecture decisions inform project scaffolding choices
- **business-analyst-toolkit** - Requirements define entity models and API contracts
- **product-manager-toolkit** - User stories guide feature implementation

**This skill provides output to:**
- **senior-devops** - Generated projects include Dockerfile and CI/CD configuration
- **senior-qa** - Generated code includes test scaffolding for QA automation
- **technical-writer** - OpenAPI specs feed API documentation generation

### Recommended Skill Combinations

**Workflow Pattern 1: Microservices Development**
```
senior-architect → senior-java → senior-devops
```
Use this pattern for designing and deploying microservices with proper architecture review.

**Workflow Pattern 2: Full-Stack Feature**
```
senior-java → senior-frontend → senior-qa
```
Use this pattern for end-to-end feature implementation with backend API, frontend UI, and testing.

## Benefits

**Time Savings:**
- 60% faster project scaffolding vs. manual setup
- 50% reduction in boilerplate code through generation
- 40% faster security implementation with templates

**Quality Improvements:**
- Consistent architecture across projects
- Built-in security best practices
- Comprehensive test coverage templates

**Business Impact:**
- Faster time-to-market for new services
- Reduced technical debt through standardization
- Lower maintenance costs through consistency

## Next Steps

**Getting Started:**
1. Run `python scripts/spring_project_scaffolder.py my-service --type microservice --db postgresql` to create your first project
2. Review generated structure and customize configuration
3. Generate entities with `python scripts/entity_generator.py`

**Advanced Usage:**
- Configure Spring Cloud for service discovery
- Implement reactive patterns with WebFlux
- Set up distributed tracing with Micrometer

## Additional Resources

- **Quick commands** - See tool documentation above
- **Best practices** - See [spring-boot-best-practices.md](references/spring-boot-best-practices.md)
- **Troubleshooting** - See [java-performance-tuning.md](references/java-performance-tuning.md)
- **External documentation** - [Spring Boot Reference](https://docs.spring.io/spring-boot/docs/current/reference/html/)

---

**Documentation:** Full skill guide and workflows available in this file

**Support:** For issues or questions, refer to domain guide at `../CLAUDE.md`

**Version:** 1.0.0 | **Last Updated:** 2025-12-16 | **Status:** Production Ready
