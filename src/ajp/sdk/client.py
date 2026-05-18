"""AJP Agent SDK - Lightweight Python client for agents to interact with AJP server."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("ajp.sdk")


class EventType(str, Enum):
    """Event types for journal entries."""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    COMMIT = "commit"
    ERROR = "error"
    SYSTEM = "system"


class Priority(int, Enum):
    """Entry priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class JournalEntry:
    """A journal entry returned from the server."""
    entry_id: str
    agent_id: str
    event_type: str
    entry_data: Dict[str, Any]
    priority: int
    metadata: Dict[str, Any]
    timestamp: str
    entry_hash: str
    signature: str
    sequence_number: int
    status: str


@dataclass
class ServerHealth:
    """Server health status."""
    status: str
    uptime_seconds: float
    total_entries: int
    active_agents: int
    backpressure_level: str
    buffer_utilization: float


@dataclass
class AgentConfig:
    """Configuration for the AJP client."""
    agent_id: str
    server_url: str = "http://localhost:8000"
    timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 1.0
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    default_priority: Priority = Priority.NORMAL
    auto_retry: bool = True
    batch_size: int = 10
    batch_interval: float = 0.5


class AJPClient:
    """
    Lightweight client for agents to log to the AJP server.

    Usage:
        client = AJPClient(agent_id="my-agent", server_url="http://localhost:8000")
        client.log_thought("Processing user request...")
        client.log_tool_call("search", {"query": "hello world"})
        client.log_error("Connection failed", {"retry_count": 3})
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.server_url,
            timeout=config.timeout,
            headers={
                "X-Agent-ID": config.agent_id,
                "X-Session-ID": config.session_id or str(uuid.uuid4()),
            },
        )
        self._batch_buffer: List[Dict[str, Any]] = []
        self._sequence = 0
        self._started = False

    async def start(self):
        """Initialize the client and verify server connectivity."""
        if self._started:
            return
        try:
            health = await self._client.get("/health")
            health.raise_for_status()
            self._started = True
            logger.info(f"AJP Client connected to {self.config.server_url}")
        except Exception as e:
            logger.warning(f"Server health check failed: {e}")
            self._started = False

    async def stop(self):
        """Flush any pending entries and close the client."""
        if self._batch_buffer:
            await self._flush_batch()
        await self._client.aclose()
        self._started = False

    async def log(self, event_type: EventType, entry_data: Dict[str, Any],
                  priority: Optional[Priority] = None,
                  metadata: Optional[Dict[str, Any]] = None) -> JournalEntry:
        """
        Log a journal entry to the server.

        This is the primary method for logging. For convenience, use the
        specialized methods like log_thought(), log_tool_call(), etc.
        """
        if not priority:
            priority = self.config.default_priority

        entry_metadata = dict(self.config.metadata)
        if metadata:
            entry_metadata.update(metadata)

        payload = {
            "agent_id": self.config.agent_id,
            "event_type": event_type.value,
            "entry_data": entry_data,
            "priority": priority.value,
            "metadata": entry_metadata,
        }

        try:
            response = await self._client.post("/entries", json=payload)
            response.raise_for_status()
            data = response.json()
            return self._parse_entry(data)
        except Exception as e:
            logger.error(f"Failed to log entry: {e}")
            raise

    async def log_batch(self, entries: List[Dict[str, Any]]) -> List[JournalEntry]:
        """Log multiple entries in a single batch request."""
        results = []
        for entry in entries:
            try:
                result = await self.log(
                    event_type=EventType(entry["event_type"]),
                    entry_data=entry.get("entry_data", {}),
                    priority=Priority(entry.get("priority", 5)),
                    metadata=entry.get("metadata"),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to log batch entry: {e}")
        return results

    async def log_thought(self, content: str, **kwargs) -> JournalEntry:
        """Log a thought/reasoning step."""
        return await self.log(
            EventType.THOUGHT,
            {"content": content},
            metadata=kwargs,
        )

    async def log_action(self, action_name: str, arguments: Dict[str, Any], **kwargs) -> JournalEntry:
        """Log an action/tool call."""
        return await self.log(
            EventType.ACTION,
            {"action_name": action_name, "arguments": arguments},
            metadata=kwargs,
        )

    async def log_observation(self, source: str, result: Any, **kwargs) -> JournalEntry:
        """Log an observation/tool result."""
        return await self.log(
            EventType.OBSERVATION,
            {"source": source, "result": result},
            metadata=kwargs,
        )

    async def log_commit(self, content: str, **kwargs) -> JournalEntry:
        """Log a commit point (checkpoint)."""
        return await self.log(
            EventType.COMMIT,
            {"content": content},
            priority=Priority.HIGH,
            metadata=kwargs,
        )

    async def log_error(self, error_message: str, details: Optional[Dict[str, Any]] = None, **kwargs) -> JournalEntry:
        """Log an error event."""
        entry_data = {"error": error_message}
        if details:
            entry_data.update(details)
        return await self.log(
            EventType.ERROR,
            entry_data,
            priority=Priority.HIGH,
            metadata=kwargs,
        )

    async def log_audit(self, action: str, target: str, **kwargs) -> JournalEntry:
        """Log an audit event."""
        return await self.log(
            EventType.AUDIT,
            {"action": action, "target": target},
            priority=Priority.HIGH,
            metadata=kwargs,
        )

    async def read_entries(self, limit: int = 100, offset: int = 0) -> List[JournalEntry]:
        """Read journal entries for this agent."""
        response = await self._client.get(
            "/entries",
            params={
                "agent_id": self.config.agent_id,
                "limit": limit,
                "offset": offset,
            },
        )
        response.raise_for_status()
        return [self._parse_entry(e) for e in response.json()]

    async def verify_chain(self) -> Dict[str, Any]:
        """Verify the integrity of this agent's journal chain."""
        response = await self._client.post(f"/verify/{self.config.agent_id}")
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> ServerHealth:
        """Check server health."""
        response = await self._client.get("/health")
        response.raise_for_status()
        data = response.json()
        return ServerHealth(**data)

    def _parse_entry(self, data: Dict[str, Any]) -> JournalEntry:
        """Parse a journal entry from server response."""
        return JournalEntry(
            entry_id=data["entry_id"],
            agent_id=data["agent_id"],
            event_type=data["event_type"],
            entry_data=data.get("entry_data", {}),
            priority=data.get("priority", 5),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", ""),
            entry_hash=data.get("entry_hash", ""),
            signature=data.get("signature", ""),
            sequence_number=data.get("sequence_number", 0),
            status=data.get("status", "pending"),
        )

    async def _flush_batch(self):
        """Flush the batch buffer to the server."""
        if not self._batch_buffer:
            return
        batch = self._batch_buffer[:self.config.batch_size]
        self._batch_buffer = self._batch_buffer[self.config.batch_size:]
        await self.log_batch(batch)


class SyncAJPClient:
    """
    Synchronous wrapper around AJPClient for agents that don't use async.

    Usage:
        client = SyncAJPClient(agent_id="my-agent")
        client.log_thought("Processing request...")
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self._async_client = AJPClient(config)
        self._loop = None

    def _get_loop(self):
        """Get or create an event loop."""
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def start(self):
        """Initialize the client."""
        loop = self._get_loop()
        loop.run_until_complete(self._async_client.start())

    def stop(self):
        """Shutdown the client."""
        loop = self._get_loop()
        loop.run_until_complete(self._async_client.stop())

    def log(self, event_type: EventType, entry_data: Dict[str, Any],
            priority: Optional[Priority] = None,
            metadata: Optional[Dict[str, Any]] = None) -> JournalEntry:
        """Log a journal entry."""
        loop = self._get_loop()
        return loop.run_until_complete(
            self._async_client.log(event_type, entry_data, priority, metadata)
        )

    def log_thought(self, content: str, **kwargs) -> JournalEntry:
        """Log a thought."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.log_thought(content, **kwargs))

    def log_action(self, action_name: str, arguments: Dict[str, Any], **kwargs) -> JournalEntry:
        """Log an action."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.log_action(action_name, arguments, **kwargs))

    def log_observation(self, source: str, result: Any, **kwargs) -> JournalEntry:
        """Log an observation."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.log_observation(source, result, **kwargs))

    def log_commit(self, content: str, **kwargs) -> JournalEntry:
        """Log a commit."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.log_commit(content, **kwargs))

    def log_error(self, error_message: str, details: Optional[Dict[str, Any]] = None, **kwargs) -> JournalEntry:
        """Log an error."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.log_error(error_message, details, **kwargs))

    def log_audit(self, action: str, target: str, **kwargs) -> JournalEntry:
        """Log an audit event."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.log_audit(action, target, **kwargs))

    def read_entries(self, limit: int = 100, offset: int = 0) -> List[JournalEntry]:
        """Read journal entries."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.read_entries(limit, offset))

    def verify_chain(self) -> Dict[str, Any]:
        """Verify chain integrity."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.verify_chain())

    def health_check(self) -> ServerHealth:
        """Check server health."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.health_check())
