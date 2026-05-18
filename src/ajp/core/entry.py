"""Core data structures for AJP journal entries."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import hashlib
import json


class EventType(Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    COMMIT = "commit"
    ERROR = "error"
    SYSTEM = "system"


@dataclass
class JournalEntry:
    agent_id: str
    event_type: EventType
    entry_data: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    entry_hash: Optional[str] = None
    parent_hash: Optional[str] = None
    signature: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    entry_id: Optional[str] = None
    priority: int = 5
    sequence_number: int = 0
    status: str = "pending"

    def __post_init__(self):
        if self.entry_id is None:
            self.entry_id = hashlib.sha256(
                f"{self.agent_id}:{self.timestamp}:{id(self)}".encode()
            ).hexdigest()[:16]

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry."""
        data = {
            "agent_id": self.agent_id,
            "event_type": self.event_type.value,
            "entry_data": self.entry_data,
            "timestamp": self.timestamp.isoformat(),
            "parent_hash": self.parent_hash,
        }
        canonical = json.dumps(data, sort_keys=True, default=str)
        self.entry_hash = hashlib.sha256(canonical.encode()).hexdigest()
        return self.entry_hash

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "event_type": self.event_type.value,
            "entry_data": self.entry_data,
            "timestamp": self.timestamp.isoformat(),
            "entry_hash": self.entry_hash,
            "parent_hash": self.parent_hash,
            "signature": self.signature,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JournalEntry":
        data = data.copy()
        data["event_type"] = EventType(data["event_type"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)
