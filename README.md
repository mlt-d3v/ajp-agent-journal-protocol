# Agent Journal Protocol (AJP)

Tamper-evident, compliance-ready journaling for autonomous AI agents.

## Quick Start

```bash
# Install
pip install ajp-agent-journal-protocol[all]

# Start the server
python -m ajp.server.app --host 0.0.0.0 --port 8000

# Use the SDK
from ajp.sdk import AJPClient, AgentConfig

config = AgentConfig(agent_id="my-agent", server_url="http://localhost:8000")
client = AJPClient(config)
await client.start()
await client.log_thought("Processing request...")
await client.log_action("search", {"query": "hello"})
await client.log_error("Connection failed")
```

## Architecture

Six phases of agent journaling:

| Phase | Module | Tests | Description |
|-------|--------|-------|-------------|
| 1 | Core | 27 | Hash chaining, Ed25519 signatures, Merkle trees, injection protection, rate limiting, data retention |
| 2 | Service | 35 | Async journal service, priority buffer, batch writer, backpressure, storage backends |
| 3 | Security | 49 | Vault client, HSM, Merkle anchoring (Local/GitHub/IPFS/Blockchain), security orchestrator |
| 4 | Analytics | 74 | Semantic search, failure interceptor (7 patterns), ops console, compliance gap analyzer |
| 5 | Workflow | 54 | Temporal-like workflow engine, OpenTelemetry tracing, metrics exporter |
| 6 | Server+SDK | 24 | FastAPI REST server, async/sync Python SDK clients |

Total: 223 passing tests

## API Endpoints

- `GET /health` - Server health status
- `POST /entries` - Create journal entry
- `GET /entries` - Read entries (filter by agent_id, event_type)
- `GET /stats` - Server statistics
- `GET /agents` - List known agents
- `GET /backpressure` - Backpressure status
- `POST /flush` - Manual buffer flush
- `POST /verify/{agent_id}` - Verify chain integrity

## SDK Clients

Async client for async agents:
```python
client = AJPClient(AgentConfig(agent_id="agent-1"))
await client.log_thought("Thinking...")
```

Sync client for blocking agents:
```python
client = SyncAJPClient(AgentConfig(agent_id="agent-1"))
client.log_thought("Thinking...")
```

## Compliance

Built-in gap analysis for SOC 2, GDPR, and OWASP LLM Top 10.
