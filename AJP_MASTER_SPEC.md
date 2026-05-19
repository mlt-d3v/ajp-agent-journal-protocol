# AJP (Agent Journal Protocol) - Master Specification

## Overview
AJP is a tamper-evident, compliance-ready journaling protocol for AI agents. It provides cryptographic integrity, secret management, prompt injection protection, rate limiting, data retention, async non-blocking writes, security hardening, and analytics/monitoring.

## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Application                         │
├─────────────────────────────────────────────────────────────┤
│  Phase 4: Analytics & Monitoring                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Semantic     │ │ Failure      │ │ Ops Console          │ │
│  │ Search       │ │ Interceptor  │ │ + Gap Analyzer       │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Phase 3: Security Hardening                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Vault Client │ │ HSM Backend  │ │ Merkle Anchoring     │ │
│  │ + Orchestrator│              │ │ Service              │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Phase 2: Async Journal Service                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Write Buffer │ │ Batch Writer │ │ Storage Backend      │ │
│  │ + Backpressure│             │ │ (Mock/PostgreSQL)    │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: Core Library                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Chain (SHA-  │ │ Secret       │ │ Prompt Injection     │ │
│  │ 256+Ed25519) │ │ Manager      │ │ Protection           │ │
│  │ Merkle Tree  │ │ Vault+RBAC   │ │ Rate Limiting        │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Phase 1: Core Library (DONE - 27 tests)
### Gap 1: Log Immutability
- SHA-256 hash chaining between entries
- Ed25519 digital signatures per entry
- Merkle tree for batch verification
- Tamper detection via chain validation

### Gap 2: Secret Management
- HashiCorp Vault integration (mock for CI)
- RBAC for agent access control
- Token rotation and revocation
- Secret encryption at rest

### Gap 3: Prompt Injection Protection
- 4-layer sanitization pipeline
- 15+ injection pattern detection
- Quarantine for suspicious entries
- Unicode normalization

### Gap 4: Rate Limiting
- Token bucket algorithm
- Circuit breaker pattern
- 5-level backpressure
- Per-agent limits

### Gap 5: Data Retention
- Hot/Warm/Cold tiering
- GDPR-compliant shredding
- PII masking
- Audit trail

## Phase 2: Async Journal Service (DONE - 35 tests)
### Non-blocking Writes
- In-memory write buffer with priority queue
- Background batch writer with retry
- Configurable batch size/time threshold
- At-least-once delivery guarantee

### Backpressure Management
- 5 levels: OK, LOW, MEDIUM, HIGH, CRITICAL
- Auto-recovery when buffer drains
- Agent notification via callbacks
- Graceful shutdown with buffer drain

### Storage Backend
- Abstract StorageBackend interface
- MockStorage for testing
- PostgreSQLStorage placeholder

## Phase 3: Security Hardening (DONE - 49 tests)
### Production Vault Integration
- HashiCorp Vault client with AppRole/Kubernetes/Token auth
- TLS support
- Auto-renewal
- MockVaultAdapter for CI

### HSM Integration
- Abstract HSMBackend interface
- SoftwareHSM (production-ready pattern)
- CloudHSM placeholder (AWS/Azure/GCP)
- Key lifecycle: generate, sign, verify, wrap/unwrap, rotate, destroy

### Merkle Root Anchoring
- Local, GitHub, IPFS, Blockchain backends
- Tamper-detectable provenance
- Root verification

### Security Orchestrator
- Unified key provisioning, signing, rotation
- Full security audit trail
- Penetration test scenarios

## Phase 4: Analytics & Monitoring (DONE - 74 tests)
### Semantic Search
- pgvector similarity search
- Hash-based embeddings fallback
- Agent/event-type/time filters

### Failure Interceptor Agent
- 7 failure detection patterns
- Auto-remediation (throttle, quarantine, circuit break, key rotate)
- Cascading failure detection

### Ops Console
- Real-time metrics collection
- Alerting rules with warning/critical thresholds
- Health status (healthy/degraded/unhealthy)
- Prometheus export

### Gap Analysis
- SOC 2 (8 controls), GDPR (5 controls), OWASP LLM Top 10 (7 controls)
- Text/JSON/Markdown report generation
- ~80% compliance baseline

## Phase 5: Temporal Workflow + OpenTelemetry (DONE - 54 tests)
### Temporal Workflow Engine
- Workflow definitions for agent journaling
- Checkpoint and recovery (savepoint, barrier, compensation)
- Saga pattern for distributed transactions
- Retry policies with exponential backoff

### OpenTelemetry Bridge
- Distributed tracing across agent nodes (Span, Trace)
- Span context propagation (parent/child)
- Metrics export (counters, gauges, histograms)
- Log correlation via trace IDs

## Phase 6: REST API Server + Agent SDK (DONE - 24 tests)
### FastAPI REST Server
- Health check, entry CRUD, stats, agents, backpressure endpoints
- Buffer flush and chain verification endpoints
- CORS middleware, lifecycle management
- Pydantic request/response models

### Agent SDK Client
- AJPClient (async) - log_thought, log_action, log_observation, log_commit, log_error
- SyncAJPClient (sync wrapper) - same API for blocking agents
- AgentConfig with server URL, timeout, retries, session ID
- Batch logging support
- Chain verification and health check

## Phase 7: Production Integrations (DONE - 69 tests)
### Real PostgreSQL Storage
- asyncpg connection pooling, schema migrations, proper indexing
- Bulk insert support, transaction safety, retry logic
- Configurable host/port/database/pool/SSL

### HashiCorp Vault Client
- AppRole/Kubernetes/Token/LDAP/AWS IAM auth methods
- KV v2 secret engine, Transit engine for encryption
- Dynamic DB credentials, auto token renewal
- Mock fallback when hvac unavailable

### Temporal Workflow Engine
- Checkpoint-based state persistence
- Saga pattern with compensation
- Activity/workflow registration
- Mock mode for testing without Temporal server

### OpenTelemetry OTLP Exporter
- Distributed tracing with span hierarchy
- Metrics: counters, gauges, histograms
- Structured logging with trace context
- Mock mode for testing without collector

## Phase 8: CI/CD Pipeline (DONE - 24 tests)
### GitHub Actions Workflows
- CI pipeline: lint (ruff, mypy), test (Python 3.9-3.12 matrix), security (bandit, safety), build, integration (PostgreSQL)
- Release pipeline: tag-triggered PyPI publish with OIDC
- Pre-commit hooks: ruff, ruff-format, mypy, bandit

### Docker Infrastructure
- Multi-stage Dockerfile (builder + runtime, non-root user)
- Docker Compose: AJP server, PostgreSQL, Vault, OTel Collector, Grafana
- Health checks and service dependencies

### Build & Dev Tooling
- pyproject.toml with setuptools, optional deps, tool configs (ruff, mypy, pytest)
- Makefile: install, test, lint, security, build, docker-up/down, server, release
- OpenTelemetry collector config (traces, metrics, logs)

## Phase 10: Compliance Audits (DONE - 15 tests)

### Evidence-Based Compliance Checking
- ComplianceAuditor runs live evidence collection against AJP components
- SOC 2 (7 controls): log immutability, digital signatures, encryption at rest, monitoring, key rotation
- GDPR (4 controls): right to erasure, data minimization/PII masking, security of processing
- OWASP LLM (4 controls): prompt injection, sensitive info disclosure, prompt leakage protection
- Each control has verifiable EvidenceItem with pass/fail + detail
- Report generation in text and JSON formats
- Combined multi-framework report generation

## Phase 9: Performance Benchmarks (DONE - 9 tests)

### Benchmark Harness
- Benchmark class with warmup, iteration control, latency measurement
- P50/P95/P99 latency percentiles
- Memory delta tracking (when psutil available)
- Text and JSON report generation

### Benchmarks
- JournalEntry creation throughput (773K ops/sec)
- Entry hash computation (399K ops/sec)
- Chain append throughput (10+ ops/sec with signing)
- Chain verification latency (100 entries: ~71ms P50, 1000 entries: ~700ms P50)
- Merkle tree add throughput and proof generation
- Semantic search query latency
- Full benchmark suite with report file output

## Test Summary
| Phase | Tests | Status |
|-------|-------|--------|
| 1     | 27    | ✅ PASS |
| 2     | 35    | ✅ PASS |
| 3     | 49    | ✅ PASS |
| 4     | 74    | ✅ PASS |
| 5     | 54    | ✅ PASS |
| 6     | 24    | ✅ PASS |
| 7     | 69    | ✅ PASS |
| 8     | 24    | ✅ PASS |
| 9     | 9     | ✅ PASS |
| 10    | 15    | ✅ PASS |
| Total | 340   | ✅ 340 PASS |

## Packaging
- pyproject.toml with setuptools
- Optional deps: dev, server, sdk, postgres, vault, temporal, opentelemetry, all
- Installable via pip

## Pitfalls
1. Python 3.9 asyncio: Set event loop policy explicitly in async test classes
2. ed25519 library: `verify()` takes `(sig, msg)` order, not `(msg, sig)`
3. MockStorage `read_entries()` default limit=100 silently truncates
4. Relative imports required for package resolution (no absolute `ajp.` imports)
5. JournalEntry uses `entry_data` dict, not `content` string
6. JournalEntry uses `event_type` field name, not `entry_type`
7. Pydantic models reject None for non-Optional string fields
8. SDK EventType enum must match core EventType enum values
9. Integration clients do NOT auto-connect on __init__ -- must call connect() first
10. All integrations have mock mode enabled by default for CI/testing
11. YAML `on:` key parses as boolean `True` in PyYAML -- quote as `"on":` in test assertions
12. `tomllib` (Python 3.11+) requires binary file mode (`"rb"`)
