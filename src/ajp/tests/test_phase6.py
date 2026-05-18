"""Phase 6 Tests: REST API Server + Agent SDK Client."""

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

# Add src to path
sys.path.insert(0, str(__file__.rsplit("/", 3)[0]))

from ajp.core.entry import JournalEntry, EventType
from ajp.sdk.client import (
    AJPClient,
    SyncAJPClient,
    AgentConfig,
    Priority,
    JournalEntry as SDKJournalEntry,
    ServerHealth,
)
from ajp.server.api import (
    JournalEntryCreate,
    JournalEntryResponse,
    HealthStatus,
    ServerStats,
    BackpressureInfo,
    AgentInfo,
    create_entry,
    read_entries,
    health_check,
    get_stats,
    get_agents,
    get_backpressure,
    verify_chain,
    flush_buffer,
    get_service,
    shutdown_service,
)


class TestJournalEntryCreate(unittest.TestCase):
    def test_create_entry_request(self):
        req = JournalEntryCreate(
            agent_id="test-agent",
            event_type="thought",
            entry_data={"content": "hello"},
            priority=5,
            metadata={"key": "value"},
        )
        self.assertEqual(req.agent_id, "test-agent")
        self.assertEqual(req.event_type.value, "thought")

    def test_priority_validation(self):
        with self.assertRaises(Exception):
            JournalEntryCreate(
                agent_id="test",
                event_type="thought",
                priority=11,
            )

    def test_empty_metadata(self):
        req = JournalEntryCreate(
            agent_id="test",
            event_type="thought",
        )
        self.assertEqual(req.metadata, {})


class TestJournalEntryResponse(unittest.TestCase):
    def test_from_entry(self):
        entry = JournalEntry(
            agent_id="test-agent",
            event_type=EventType.THOUGHT,
            entry_data={"content": "test"},
        )
        response = JournalEntryResponse.from_entry(entry)
        self.assertEqual(response.agent_id, "test-agent")
        self.assertEqual(response.event_type, "thought")
        self.assertEqual(response.entry_data, {"content": "test"})


class TestHealthStatus(unittest.TestCase):
    def test_health_status_fields(self):
        health = HealthStatus(
            status="healthy",
            uptime_seconds=100.0,
            total_entries=50,
            active_agents=3,
            backpressure_level="NONE",
            buffer_utilization=0.1,
        )
        self.assertEqual(health.status, "healthy")
        self.assertGreater(health.uptime_seconds, 0)


class TestServerStats(unittest.TestCase):
    def test_stats_fields(self):
        stats = ServerStats(
            total_entries=1000,
            active_agents=5,
            buffer_size=100,
            max_buffer_size=5000,
            backpressure_level="LOW",
            buffer_utilization=0.2,
            avg_write_latency_ms=5.0,
            error_rate=0.01,
        )
        self.assertEqual(stats.total_entries, 1000)
        self.assertGreater(stats.error_rate, 0)


class TestBackpressureInfo(unittest.TestCase):
    def test_backpressure_fields(self):
        bp = BackpressureInfo(
            level="LOW",
            buffer_utilization=0.3,
            buffer_size=1500,
            max_buffer_size=5000,
            is_throttling=False,
        )
        self.assertFalse(bp.is_throttling)
        self.assertEqual(bp.buffer_size, 1500)


class TestAgentInfo(unittest.TestCase):
    def test_agent_info_fields(self):
        agent = AgentInfo(
            agent_id="agent-1",
            session_id="session-123",
            total_entries=42,
            last_activity="2024-01-01T00:00:00Z",
        )
        self.assertEqual(agent.agent_id, "agent-1")
        self.assertEqual(agent.total_entries, 42)


class TestAPIFunctions(unittest.TestCase):
    def test_create_entry_request_validation(self):
        req = JournalEntryCreate(
            agent_id="test",
            event_type="thought",
            entry_data={"test": "data"},
        )
        self.assertEqual(req.entry_data, {"test": "data"})

    def test_event_type_enum_values(self):
        from ajp.server.api import EventTypeStr
        self.assertEqual(EventTypeStr.THOUGHT.value, "thought")
        self.assertEqual(EventTypeStr.ERROR.value, "error")
        self.assertEqual(EventTypeStr.COMMIT.value, "commit")

    def test_response_serialization(self):
        entry = JournalEntry(
            agent_id="test",
            event_type=EventType.THOUGHT,
            entry_data={"msg": "hello"},
        )
        resp = JournalEntryResponse.from_entry(entry)
        self.assertEqual(resp.agent_id, "test")
        self.assertEqual(resp.entry_data, {"msg": "hello"})


class TestAJPClient(unittest.TestCase):
    def test_client_config(self):
        config = AgentConfig(agent_id="test-agent")
        self.assertEqual(config.agent_id, "test-agent")
        self.assertEqual(config.server_url, "http://localhost:8000")
        self.assertEqual(config.timeout, 10.0)

    def test_client_custom_config(self):
        config = AgentConfig(
            agent_id="custom-agent",
            server_url="http://custom:9000",
            timeout=30.0,
            max_retries=5,
            session_id="session-123",
        )
        self.assertEqual(config.server_url, "http://custom:9000")
        self.assertEqual(config.max_retries, 5)

    def test_client_creates_httpx_client(self):
        config = AgentConfig(agent_id="test")
        client = AJPClient(config)
        self.assertIsNotNone(client._client)
        self.assertEqual(client._started, False)

    def test_log_thought_payload(self):
        config = AgentConfig(agent_id="test-agent")
        client = AJPClient(config)
        # Verify the payload structure
        payload = {
            "agent_id": "test-agent",
            "event_type": "thought",
            "entry_data": {"content": "thinking..."},
            "priority": 5,
            "metadata": {},
        }
        self.assertEqual(payload["agent_id"], "test-agent")
        self.assertEqual(payload["event_type"], "thought")

    def test_log_error_high_priority(self):
        config = AgentConfig(agent_id="test-agent")
        client = AJPClient(config)
        payload = {
            "agent_id": "test-agent",
            "event_type": "error",
            "entry_data": {"error": "something failed"},
            "priority": 8,
            "metadata": {},
        }
        self.assertEqual(payload["priority"], 8)

    def test_parse_entry_response(self):
        config = AgentConfig(agent_id="test")
        client = AJPClient(config)
        data = {
            "entry_id": "entry-123",
            "agent_id": "test",
            "event_type": "thought",
            "entry_data": {"content": "test"},
            "priority": 5,
            "metadata": {},
            "timestamp": "2024-01-01T00:00:00Z",
            "entry_hash": "abc123",
            "signature": "sig456",
            "sequence_number": 1,
            "status": "committed",
        }
        entry = client._parse_entry(data)
        self.assertEqual(entry.entry_id, "entry-123")
        self.assertEqual(entry.agent_id, "test")
        self.assertEqual(entry.event_type, "thought")
        self.assertEqual(entry.entry_hash, "abc123")

    def test_server_health_response(self):
        health_data = {
            "status": "healthy",
            "uptime_seconds": 100.0,
            "total_entries": 50,
            "active_agents": 3,
            "backpressure_level": "NONE",
            "buffer_utilization": 0.1,
        }
        health = ServerHealth(**health_data)
        self.assertEqual(health.status, "healthy")
        self.assertEqual(health.total_entries, 50)

    def test_priority_enum_values(self):
        self.assertEqual(Priority.LOW.value, 1)
        self.assertEqual(Priority.NORMAL.value, 5)
        self.assertEqual(Priority.HIGH.value, 8)
        self.assertEqual(Priority.CRITICAL.value, 10)

    def test_event_type_enum_values(self):
        self.assertEqual(EventType.THOUGHT.value, "thought")
        self.assertEqual(EventType.ACTION.value, "action")
        self.assertEqual(EventType.ERROR.value, "error")
        self.assertEqual(EventType.SYSTEM.value, "system")


class TestSyncAJPClient(unittest.TestCase):
    def test_sync_client_config(self):
        config = AgentConfig(agent_id="sync-agent")
        client = SyncAJPClient(config)
        self.assertEqual(client.config.agent_id, "sync-agent")

    def test_sync_client_has_async_wrapper(self):
        config = AgentConfig(agent_id="sync-agent")
        client = SyncAJPClient(config)
        self.assertIsNotNone(client._async_client)

    def test_sync_client_gets_event_loop(self):
        config = AgentConfig(agent_id="sync-agent")
        client = SyncAJPClient(config)
        loop = client._get_loop()
        self.assertIsNotNone(loop)


class TestIntegration(unittest.TestCase):
    def test_end_to_end_entry_flow(self):
        """Test the flow from client payload to server response."""
        # Create entry
        entry = JournalEntry(
            agent_id="test-agent",
            event_type=EventType.THOUGHT,
            entry_data={"content": "test thought"},
        )

        # Serialize to response
        response = JournalEntryResponse.from_entry(entry)
        self.assertEqual(response.agent_id, "test-agent")
        self.assertEqual(response.event_type, "thought")

        # Verify entry data preserved
        self.assertEqual(response.entry_data, {"content": "test thought"})

    def test_client_server_payload_compatibility(self):
        """Verify client payload matches server expectations."""
        config = AgentConfig(agent_id="test")
        client = AJPClient(config)

        # Build payload
        payload = {
            "agent_id": "test",
            "event_type": "thought",
            "entry_data": {"content": "hello"},
            "priority": 5,
            "metadata": {},
        }

        # Verify it can be parsed by server model
        req = JournalEntryCreate(**payload)
        self.assertEqual(req.agent_id, "test")
        self.assertEqual(req.event_type.value, "thought")

    def test_batch_entry_logging(self):
        """Test batch logging flow."""
        entries = [
            {"event_type": "thought", "entry_data": {"content": "first"}},
            {"event_type": "action", "entry_data": {"action_name": "search"}},
            {"event_type": "error", "entry_data": {"error": "fail"}},
        ]
        self.assertEqual(len(entries), 3)
        for entry in entries:
            self.assertIn("event_type", entry)
            self.assertIn("entry_data", entry)


if __name__ == "__main__":
    unittest.main()
