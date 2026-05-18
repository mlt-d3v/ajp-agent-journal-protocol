"""AJP REST API Server - FastAPI server wrapping the async journal service."""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..core.entry import EventType, JournalEntry
from ..service.journal import AsyncJournalService, JournalConfig
from ..service.storage import MockStorage

logger = logging.getLogger("ajp.server")


class EventTypeStr(str, Enum):
    """EventType as string for API."""
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    COMMIT = "commit"
    USER_INPUT = "user_input"
    SYSTEM = "system"
    ERROR = "error"
    AUDIT = "audit"


class JournalEntryCreate(BaseModel):
    """Request body for creating a journal entry."""
    agent_id: str
    event_type: EventTypeStr
    entry_data: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=0, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JournalEntryResponse(BaseModel):
    """Response for a journal entry."""
    entry_id: str
    agent_id: str
    event_type: str
    entry_data: dict[str, Any]
    priority: int
    metadata: dict[str, Any]
    timestamp: str
    entry_hash: Optional[str] = None
    signature: Optional[str] = None
    sequence_number: int
    status: str

    @classmethod
    def from_entry(cls, entry: JournalEntry) -> "JournalEntryResponse":
        return cls(
            entry_id=entry.entry_id,
            agent_id=entry.agent_id,
            event_type=entry.event_type.value if hasattr(entry.event_type, 'value') else str(entry.event_type),
            entry_data=entry.entry_data,
            priority=entry.priority,
            metadata=entry.metadata,
            timestamp=entry.timestamp.isoformat() if isinstance(entry.timestamp, datetime) else str(entry.timestamp),
            entry_hash=entry.entry_hash,
            signature=entry.signature,
            sequence_number=entry.sequence_number,
            status=entry.status,
        )


class AgentInfo(BaseModel):
    """Agent information."""
    agent_id: str
    session_id: Optional[str]
    total_entries: int
    last_activity: Optional[str]


class HealthStatus(BaseModel):
    """Server health status."""
    status: str
    uptime_seconds: float
    total_entries: int
    active_agents: int
    backpressure_level: str
    buffer_utilization: float


class BackpressureInfo(BaseModel):
    """Backpressure information."""
    level: str
    buffer_utilization: float
    buffer_size: int
    max_buffer_size: int
    is_throttling: bool


class ServerStats(BaseModel):
    """Server statistics."""
    total_entries: int
    active_agents: int
    buffer_size: int
    max_buffer_size: int
    backpressure_level: str
    buffer_utilization: float
    avg_write_latency_ms: float
    error_rate: float


class QueryParams(BaseModel):
    """Query parameters for reading entries."""
    agent_id: Optional[str] = None
    event_type: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# Global service instance
_journal_service: Optional[AsyncJournalService] = None
_start_time: Optional[datetime] = None


async def get_service() -> AsyncJournalService:
    """Get or create the global journal service."""
    global _journal_service
    if _journal_service is None:
        storage = MockStorage()
        config = JournalConfig(
            buffer_size=5000,
            batch_size=50,
            flush_interval=0.5,
            max_retries=3,
        )
        _journal_service = AsyncJournalService(storage=storage, config=config)
        await _journal_service.start()
        global _start_time
        _start_time = datetime.now(timezone.utc)
    return _journal_service


async def shutdown_service():
    """Shutdown the global journal service."""
    global _journal_service
    if _journal_service is not None:
        await _journal_service.stop()
        _journal_service = None


async def health_check() -> HealthStatus:
    """Check server health."""
    service = await get_service()
    uptime = (datetime.now(timezone.utc) - _start_time).total_seconds() if _start_time else 0
    entries = await service.storage.read_entries(limit=1)
    backpressure = service.backpressure_monitor.current_level
    buffer_util = service.backpressure_monitor.buffer_utilization

    return HealthStatus(
        status="healthy" if backpressure.level != "CRITICAL" else "degraded",
        uptime_seconds=uptime,
        total_entries=len(entries),
        active_agents=len({e.agent_id for e in entries}),
        backpressure_level=backpressure.level,
        buffer_utilization=buffer_util,
    )


async def create_entry(request: JournalEntryCreate) -> JournalEntryResponse:
    """Create a new journal entry."""
    service = await get_service()
    event_type = EventType(request.event_type.value)
    entry_data = request.entry_data
    metadata = request.metadata

    entry = await service.append_entry(
        agent_id=request.agent_id,
        event_type=event_type,
        entry_data=entry_data,
        priority=request.priority,
        metadata=metadata,
    )
    return JournalEntryResponse.from_entry(entry)


async def read_entries(agent_id: Optional[str] = None, event_type: Optional[str] = None,
                       limit: int = 100, offset: int = 0) -> list[JournalEntryResponse]:
    """Read journal entries with optional filters."""
    service = await get_service()
    entries = await service.storage.read_entries(
        agent_id=agent_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return [JournalEntryResponse.from_entry(e) for e in entries]


async def get_stats() -> ServerStats:
    """Get server statistics."""
    service = await get_service()
    entries = await service.storage.read_entries(limit=10000)
    backpressure = service.backpressure_monitor.current_level

    agent_ids = {e.agent_id for e in entries}
    error_count = sum(1 for e in entries if e.event_type == EventType.ERROR)

    return ServerStats(
        total_entries=len(entries),
        active_agents=len(agent_ids),
        buffer_size=service.backpressure_monitor.current_buffer_size,
        max_buffer_size=service.config.buffer_size,
        backpressure_level=backpressure.level,
        buffer_utilization=service.backpressure_monitor.buffer_utilization,
        avg_write_latency_ms=0.0,
        error_rate=error_count / len(entries) if entries else 0.0,
    )


async def get_agents() -> list[AgentInfo]:
    """Get list of known agents."""
    service = await get_service()
    entries = await service.storage.read_entries(limit=10000)

    agents = {}
    for entry in entries:
        if entry.agent_id not in agents:
            agents[entry.agent_id] = {
                "agent_id": entry.agent_id,
                "total_entries": 0,
                "last_activity": entry.timestamp,
            }
        agents[entry.agent_id]["total_entries"] += 1
        if entry.timestamp > agents[entry.agent_id]["last_activity"]:
            agents[entry.agent_id]["last_activity"] = entry.timestamp

    result = []
    for agent in agents.values():
        result.append(AgentInfo(
            agent_id=agent["agent_id"],
            session_id=None,
            total_entries=agent["total_entries"],
            last_activity=agent["last_activity"].isoformat() if hasattr(agent["last_activity"], 'isoformat') else str(agent["last_activity"]),
        ))
    return result


async def get_backpressure() -> BackpressureInfo:
    """Get backpressure status."""
    service = await get_service()
    bp = service.backpressure_monitor
    return BackpressureInfo(
        level=bp.current_level.level,
        buffer_utilization=bp.buffer_utilization,
        buffer_size=bp.current_buffer_size,
        max_buffer_size=service.config.buffer_size,
        is_throttling=bp.is_throttling(),
    )


async def verify_chain(agent_id: str) -> dict[str, Any]:
    """Verify the integrity of an agent's journal chain."""
    service = await get_service()
    entries = await service.storage.read_entries(agent_id=agent_id, limit=10000)

    if not entries:
        return {"valid": True, "message": "No entries to verify"}

    valid = True
    last_hash = None
    for entry in entries:
        expected_hash = entry.compute_hash()
        if last_hash is not None and expected_hash != entry.entry_hash:
            valid = False
            break
        last_hash = expected_hash

    return {
        "valid": valid,
        "agent_id": agent_id,
        "entries_checked": len(entries),
        "message": "Chain integrity verified" if valid else "Chain integrity compromised",
    }


async def flush_buffer() -> dict[str, Any]:
    """Manually trigger a buffer flush."""
    service = await get_service()
    await service.writer.flush()
    return {"status": "flushed", "buffer_size": service.backpressure_monitor.current_buffer_size}
