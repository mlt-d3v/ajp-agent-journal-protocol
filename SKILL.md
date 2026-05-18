---
name: ajp-agent-journal-protocol
version: 8.0.0
description: "Agent Journal Protocol (AJP) - tamper-evident, compliance-grade observability layer for multi-agent AI systems. 8 phases complete: core immutability, async journal, security hardening, analytics, workflow plus tracing, REST server plus SDK, production integrations (PostgreSQL, Vault, Temporal, OpenTelemetry), CI/CD pipeline. 316 tests."
category: software-development
triggers:
  - "AJP"
  - "Agent Journal Protocol"
  - "agent observability"
  - "journal immutability"
  - "agent audit trail"
  - "compliance journaling"
  - "SOC 2 agent logging"
  - "GDPR agent data"
  - "agent workflow"
  - "distributed tracing agent"
  - "CI/CD pipeline"
  - "Docker compose"
---

# AJP (Agent Journal Protocol) v0.8.0

Tamper-evident, compliance-grade observability layer for multi-agent AI systems. 8 phases, 316 tests.

## Project Location
```
~/.hermes/skills/ajp-agent-journal-protocol/
  src/ajp/                    # Source code
  src/ajp/core/               # Phase 1: Core library
  src/ajp/service/            # Phase 2: Async journal
  src/ajp/security/           # Phase 3: Security hardening
  src/ajp/analytics/          # Phase 4: Analytics and monitoring
  src/ajp/workflow/           # Phase 5: Workflow plus tracing
  src/ajp/server/             # Phase 6: REST API server
  src/ajp/sdk/                # Phase 6: Agent SDK client
  src/ajp/tests/              # All tests
  AJP_MASTER_SPEC.md          # Master specification
  pyproject.toml              # Packaging configuration
  README.md                   # Quick start guide
```

## Architecture Overview

Eight phases, 38 source files, 316 passing tests:

| Phase | Files | Tests | Key Modules |
|-------|-------|-------|-------------|
| 1: Core | 8 | 27 | JournalEntry, JournalChain, MerkleTree, SecretManager, PromptSanitizer, RateLimiter, DataRetentionManager |
| 2: Async | 5 | 35 | AsyncJournalService, WriteBuffer, BatchWriter, MockStorage, PostgreSQLStorage |
| 3: Security | 4 | 49 | VaultClient, SoftwareHSM, CloudHSM, SecurityOrchestrator, MerkleAnchoringService |
| 4: Analytics | 4 | 74 | SemanticSearchEngine, FailureInterceptor, OpsConsole, GapAnalyzer |
| 5: Workflow | 3 | 54 | WorkflowEngine, Tracer, MetricsExporter |
| 6: Server+SDK | 3 | 24 | FastAPI app, AJPClient, SyncAJPClient, AgentConfig |
| 7: Integrations | 4 | 69 | PostgresStorage, RealVaultClient, TemporalWorkflowEngine, OTLPExporter |
| 8: CI/CD | 8 | 24 | GitHub Actions, Docker, Makefile, pyproject.toml, pre-commit |
- `SyncAJPClient(config)`: Sync wrapper for blocking agents

## Phase 8: CI/CD Pipeline

Full CI/CD infrastructure for building, testing, security scanning, and releasing.

### GitHub Actions Workflows
- `ci.yml`: Lint (ruff+mypy), test matrix (Python 3.9-3.12), security (bandit+safety), build, integration with PostgreSQL service
- `release.yml`: Tag-triggered PyPI publish with OIDC authentication
- Pre-commit hooks: ruff, ruff-format, mypy, bandit

### Docker Infrastructure
- Multi-stage Dockerfile (builder + runtime, non-root user, port 8000)
- Docker Compose: AJP server, PostgreSQL 16, HashiCorp Vault, OTel Collector, Grafana
- Health checks and service dependencies

### Build & Dev Tooling
- `pyproject.toml`: setuptools, optional deps (dev, server, sdk, postgres, vault, temporal, opentelemetry, all), tool configs (ruff, mypy, pytest)
- `Makefile`: install, test, test-cov, lint, security, build, docker-up/down, server, release
- `otel-config.yaml`: OTel collector config for traces, metrics, logs pipelines

### Running CI Locally
```bash
make install        # Install with dev deps
make test           # Run all tests
make lint           # Ruff + mypy
make security       # Bandit + safety
make build          # Build wheel + sdist
make docker-up      # Start full stack
```

## Phase 7: Production Integrations

```python
from ajp.integrations import PostgresStorage, RealVaultClient, TemporalWorkflowEngine, OTLPExporter
```

**CRITICAL: None auto-connect on __init__. Always call `await client.connect()` first.**

### PostgresStorage
- `PostgresConfig(host, port, database, user, password, pool_size, ssl_enabled)`
- `PostgresStorage(config)` -- real asyncpg-backed storage with schema migrations + indexing
- `await storage.write_entry(entry_dict)` -- single entry with upsert on conflict
- `await storage.write_entries(entry_list)` -- batch write in transaction
- `await storage.read_entries(agent_id, event_type, limit, offset)` -- filtered reads
- `await storage.delete_entries(agent_id)` -- GDPR-compliant deletion
- `await storage.get_stats()` -- total entries, unique agents, schema version

### RealVaultClient
- `VaultConfig(url, token, auth_config, namespace, verify_tls, secret_path)`
- `VaultAuthConfig(auth_method, token, app_role_id, ...)` -- APP_ROLE/KUBERNETES/TOKEN/LDAP/AWS_IAM
- `await client.write_secret(path, data_dict)` -- KV v2 write
- `await client.read_secret(path)` -- KV v2 read
- `await client.encrypt_data(plaintext)` / `await client.decrypt_data(ciphertext)` -- Transit engine
- `await client.generate_dynamic_db_creds(role_name)` -- dynamic DB credentials
- Falls back to mock mode when hvac package unavailable

### TemporalWorkflowEngine
- `WorkflowConfig(server_url, namespace, task_queue, workflow_timeout)`
- `engine.register_activity(name, fn)` / `engine.register_workflow(name, fn)`
- `await engine.start_workflow(workflow_type, config)` -- returns workflow_id
- `await engine.execute_saga(workflow_id, operations)` -- saga with compensation on failure
- `await engine.add_checkpoint(workflow_id, checkpoint_dict)` -- state persistence
- Falls back to mock mode when temporalio package unavailable

### OTLPExporter
- `OTelConfig(otlp_endpoint, service_name, trace_sample_rate)`
- `exporter.start_trace(name)` -- returns trace_id
- `exporter.create_span(trace_id, name, kind, attributes)` -- creates span within trace
- `exporter.end_span(span_id, status)` -- completes span
- `exporter.record_metric(name, value, metric_type, labels)` -- COUNTER/GAUGE/HISTOGRAM
- `exporter.log_with_trace(level, message, trace_id, span_id)` -- structured logging
- Falls back to mock mode when opentelemetry package unavailable

## Verification

Run `python scripts/verify_ajp.py` from the skill directory to validate all 8 phases.

## Running Tests
```bash
cd ~/.hermes/skills/ajp-agent-journal-protocol/src
python -m pytest ajp/tests/ -v   # All 316 tests
python -m pytest ajp/tests/test_phase1.py -v  # Phase 1 only
```

## Quick Start

```python
import sys
sys.path.insert(0, "~/.hermes/skills/ajp-agent-journal-protocol/src")

from ajp.core.entry import JournalEntry, EventType
from ajp.core.chain import JournalChain

# Create immutable journal chain
chain = JournalChain("my-agent")
entry = JournalEntry(
    agent_id="my-agent",
    event_type=EventType.THOUGHT,
    entry_data={"task": "research"},
)
chain.append(entry)
assert chain.verify_chain()
```

## Phase 1: Core Library

### JournalEntry API
- Field: `event_type` (EventType enum, NOT `entry_type`)
- Field: `entry_data` (dict, NOT `content` string)
- `compute_hash()` takes NO arguments, RETURNS hash string -- assign it: `entry.entry_hash = entry.compute_hash()`
- `signature` accepts hex string

### JournalChain
- `JournalChain(agent_id)` creates chain with Ed25519 signing key
- `chain.append(entry)` -- signs and appends, links parent hash
- `chain.verify_chain()` -- validates hash chain plus signatures
- `chain.get_head_hash()` -- returns latest entry hash

### MerkleTree
- `tree.add_entry(entry)` -- adds leaf, rebuilds tree
- `tree.verify(entry_hash)` -- checks if hash is a leaf
- `tree.get_proof(entry_hash)` -- Merkle proof for verification

### SecretManager
- `sm.register_agent(agent_id, max_level)` -- returns auth token
- `sm.store_secret(agent_id, path, data, level)` -- RBAC-enforced
- `sm.retrieve_secret(agent_id, path)` -- path-scoped access
- `sm.rotate_token(agent_id)` -- revokes old, issues new
- `sm.revoke_agent(agent_id)` -- removes all access

### PromptSanitizer
- 4-layer sanitization with 15+ injection patterns
- `sanitizer.sanitize(text)` returns dict with `cleaned`, `flags`, `quarantined`, `score`
- Quarantine threshold: score >= 0.25
- `sanitizer.is_safe(text)` -- boolean check

### RateLimiter plus CircuitBreaker
- Token bucket with configurable burst size and refill rate
- 5-level backpressure: OK, LOW, MEDIUM, HIGH, CRITICAL
- Circuit breaker: CLOSED to OPEN (after threshold failures) to HALF-OPEN (after timeout)

### DataRetentionManager
- Hot (30d) to Warm (90d) to Cold (365d) to Archived (1825d) to Deleted
- `mgr.mask_pii(data)` -- redacts email, phone, name, SSN, credit card
- `mgr.shred_entry(entry_id)` -- GDPR-compliant deletion with audit trail

## Phase 2: Async Journal Service

Non-blocking async writes. Agents append; entries buffer, batch, and flush asynchronously.

```python
import asyncio
from ajp.service.journal import AsyncJournalService, JournalConfig
from ajp.service.storage import MockStorage
from ajp.core.entry import JournalEntry, EventType

async def main():
    service = AsyncJournalService(JournalConfig(
        agent_id="my-agent",
        batch_size=50,
        flush_interval=2.0,
        buffer_size=500,
        storage_backend=MockStorage(),
    ))
    await service.start()
    entry = JournalEntry(agent_id="my-agent", event_type=EventType.THOUGHT, entry_data={})
    await service.append_entry(entry)
    await service.stop()  # drains buffer

asyncio.run(main())
```

### Components
- `WriteBuffer`: Priority queue -- ERROR/COMMIT flushed before THOUGHT
- `BatchWriter`: Background loop -- flush on size threshold or time interval
- `BackpressureHandler`: 5 levels with auto-recovery
- `MockStorage` / `PostgreSQLStorage`: Pluggable backends

## Phase 3: Security Hardening

```python
import sys
sys.path.insert(0, "~/.hermes/skills/ajp-agent-journal-protocol/src")

from ajp.security.orchestrator import SecurityOrchestrator
from ajp.security.vault_client import VaultClient
from ajp.core.entry import JournalEntry, EventType

vault = VaultClient(token="test")
vault.connect()
orch = SecurityOrchestrator(vault=vault)

orch.provision_agent("agent-001")
entry = JournalEntry(agent_id="agent-001", event_type=EventType.THOUGHT, entry_data={})
entry.compute_hash()
orch.sign_entry("agent-001", entry)
assert orch.verify_entry("agent-001", entry)
orch.anchor_merkle_root(entry.entry_hash)
```

### Components
- `VaultClient`: HashiCorp Vault with AppRole/Kubernetes/Token auth. Falls back to MockVaultAdapter.
- `SoftwareHSM` / `CloudHSM`: HSMBackend interface. SoftwareHSM for dev, CloudHSM for prod.
- `SecurityOrchestrator`: Coordinates Vault plus HSM plus Anchoring. Unified key lifecycle.
- `MerkleAnchoringService`: Local, GitHub, IPFS, Blockchain backends.

## Phase 4: Analytics and Monitoring

```python
from ajp.analytics.semantic_search import SemanticSearchEngine
from ajp.analytics.failure_interceptor import FailureInterceptor
from ajp.analytics.ops_console import OpsConsole
from ajp.analytics.gap_analyzer import GapAnalyzer, ComplianceFramework

# Semantic search
engine = SemanticSearchEngine()
engine.index_entry("hash1", "agent-a", "thinking about ML", datetime.utcnow(), {})
results = engine.search("machine learning")

# Failure detection
interceptor = FailureInterceptor(error_threshold=5)
alert = interceptor.check_entry(entry)

# Ops console
console = OpsConsole()
console.record_entry(entry)
health = console.get_health_status()
prometheus = console.export_prometheus()

# Compliance
analyzer = GapAnalyzer()
findings = analyzer.run_analysis(ComplianceFramework.SOC2)
report = analyzer.generate_report("json")
```

## Phase 5: Workflow plus OpenTelemetry

Temporal-like workflow engine with checkpoints, retries, saga compensation, and distributed tracing.

```python
import asyncio
from ajp.workflow.engine import WorkflowEngine, WorkflowDefinition, WorkflowStep, WorkflowState
from ajp.workflow.otel_bridge import Tracer, MetricsExporter, SpanKind

async def main():
    engine = WorkflowEngine()
    tracer = Tracer(service_name="my-agent")
    metrics = MetricsExporter()

    defn = WorkflowDefinition(name="research")
    defn.add_step(WorkflowStep(name="search", handler=lambda ctx: "found"))
    defn.add_step(WorkflowStep(name="analyze", handler=lambda ctx: "done"))

    wid = engine.register_workflow(defn)
    tracer.start_span("workflow.start")
    result = await engine.execute(wid)
    tracer.create_child_span("workflow.complete")
    tracer.end_span()
    metrics.increment_counter("workflows_completed")

    print(engine.get_status(wid)["state"])  # "completed"

asyncio.run(main())
```

### Components
- `WorkflowEngine`: Register, execute, cancel workflows with checkpoint/retry/compensation
- `WorkflowDefinition` plus `WorkflowStep`: Declarative workflow building
- `RetryPolicy`: Exponential backoff with configurable max attempts
- `Tracer`: OpenTelemetry-compatible spans, traces, child spans
- `MetricsExporter`: Counters, gauges, histograms with label support

## Key Design Decisions

1. **Cryptographic shredding for GDPR**: Delete agent signing key, all entries become unverifiable, effectively erased.
2. **Non-blocking architecture**: Buffer to batch to async flush decouples thinking from persistence.
3. **Semantic self-improvement**: Hash-based embeddings (pgvector fallback) enable semantic search of past entries.
4. **Compliance by design**: SOC 2, GDPR, OWASP LLM Top 10 built in, not bolted on.
5. **Saga compensation**: Failed workflow steps trigger reverse-order compensation handlers.

## Pitfalls

### CRITICAL: Relative imports only
All intra-package imports MUST use relative form (`from .module import ...` or `from ..core import ...`), NEVER absolute `from ajp.core import ...`. Tests import via `src.ajp.` path which breaks absolute imports.

### ed25519 library quirks
- `SigningKey()` requires a seed: `SigningKey(os.urandom(32))` -- NOT zero-arg constructor
- `VerifyingKey.verify(sig, msg)` returns `None` on SUCCESS (not `True`) -- check `is None`
- `verify()` takes `(sig, msg)` order -- signature FIRST, message SECOND
- `sign(msg)` returns ONLY 64-byte signature (not `msg + sig`)
- Catch both `ed25519.BadSignatureError` and `AssertionError` in verify wrappers

### JournalEntry API
- `compute_hash()` takes NO arguments, returns hash -- must assign: `entry.entry_hash = entry.compute_hash()`
- Uses `event_type` not `entry_type`
- Uses `entry_data` dict not `content` string
- `json.dumps(data, sort_keys=True, default=str)` needed for datetime serialization

### RBAC SecretLevel comparison
`SecretLevel` enum values are strings ("low", "medium", "high", "critical") -- string comparison does NOT work for ordering. Use ordinal lookup: `level_order.index(level.value) > level_order.index(policy.max_level.value)`.

### MockStorage read_entries default limit
`MockStorage.read_entries()` defaults to `limit=10000` now (was 100 before). Still, always pass explicit `limit` when testing with many entries.

### PriorityEntry dataclass unpacking
`heapq.heappop()` returns the `PriorityEntry` object itself (not a tuple). Access via `item.entry`, NOT `_, entry = heapq.heappop()`.

### Async writer stop sequence
`BatchWriter.stop()`: set `_running = False` then cancel task then await drain. Do NOT drain before cancelling -- buffer lock race causes lost entries.

### Python asyncio event loop policy
In `IsolatedAsyncioTestCase` subclasses, call `asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())` in `asyncSetUp()` to prevent `asyncio.Event` objects from binding to wrong loops.

### HSM sign() raises ValueError
`SoftwareHSM.sign()` raises `ValueError` (not `KeyError`) when key is destroyed or not found.

### GapAnalyzer JSON serialization
`ComplianceFramework` and `ControlStatus` enums need `.value` for JSON serialization.

### Checkpoint serialization
`Checkpoint.to_dict()` uses `"type"` key for `checkpoint_type`; `from_dict()` must `pop("type")` before passing to constructor.

### Injection quarantine threshold
Default quarantine threshold is 0.25 (one pattern match equals quarantined). The `is_safe()` method uses the same 0.25 threshold.

### Workflow context passing
Workflow step handlers receive the context dict but results are collected in `context["step_results"]` keyed by step name. The handler return value is stored there automatically.

### Pydantic model None handling
Pydantic models reject `None` for non-Optional string fields. Use `Optional[str] = None` or provide defaults.

### SDK EventType enum alignment
The SDK `EventType` enum must match the core `EventType` enum values exactly. Mismatched values cause `AttributeError`.

### JournalEntry auto-generates entry_id
`JournalEntry` now auto-generates `entry_id` in `__post_init__` if not provided. Uses SHA-256 of agent_id + timestamp + object id.

### YAML `on:` parses as boolean
PyYAML parses `on:` as `True:` (boolean). Quote as `"on":` in YAML files when testing with `yaml.safe_load()`.

### tomllib requires binary mode
Python 3.11+ `tomllib.load()` requires binary file mode (`"rb"`), not text mode.

### SKILLS_DIR path resolution
Test files use `os.path.dirname()` 4 levels up from `__file__` to reach project root (test file -> tests -> ajp -> src -> project root).

## Roadmap
- [x] Phase 1: Core library (immutability, secrets, injection, rate limiting, retention)
- [x] Phase 2: Async journal service (non-blocking writes, backpressure)
- [x] Phase 3: Security hardening (Vault, HSM, anchoring)
- [x] Phase 4: Analytics & monitoring (semantic search, failure interceptor, ops console)
- [x] Phase 5: Workflow + tracing (Temporal engine, OpenTelemetry)
- [x] Phase 6: REST server + SDK (FastAPI, Python client)
- [x] Phase 7: Real integrations (PostgreSQL, HashiCorp Vault, Temporal, OpenTelemetry)
- [x] Phase 8: CI/CD pipeline (GitHub Actions, Docker, Makefile, pre-commit)
- [ ] Phase 9: Performance benchmarks (throughput, latency, scale)
- [ ] Phase 10: Compliance audits (SOC 2, GDPR closure)

## References
- Master spec: `AJP_MASTER_SPEC.md`
- Session details: `references/phase4-session.md`, `references/phase7-session.md`, `references/phase8-session.md`
- Verification: `scripts/verify_ajp.py` -- validates all 8 phases
