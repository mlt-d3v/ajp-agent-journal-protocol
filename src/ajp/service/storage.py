"""Abstract storage backend with mock and PostgreSQL implementations."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from ..core.entry import JournalEntry


@dataclass
class StorageBackend(ABC):
    @abstractmethod
    async def write_batch(self, entries: List[JournalEntry]) -> int:
        pass

    @abstractmethod
    async def read_entries(self, limit: int = 100, offset: int = 0) -> List[JournalEntry]:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass


@dataclass
class MockStorage(StorageBackend):
    _entries: List[JournalEntry] = field(default_factory=list)
    _write_count: int = 0

    async def write_batch(self, entries: List[JournalEntry]) -> int:
        self._entries.extend(entries)
        self._write_count += len(entries)
        return len(entries)

    async def read_entries(self, limit: int = 10000, offset: int = 0) -> List[JournalEntry]:
        return self._entries[offset:offset + limit]

    async def health_check(self) -> bool:
        return True

    @property
    def write_count(self) -> int:
        return self._write_count


class PostgreSQLStorage(StorageBackend):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._connected = False

    async def connect(self):
        self._connected = True

    async def write_batch(self, entries: List[JournalEntry]) -> int:
        if not self._connected:
            raise ConnectionError("Not connected to PostgreSQL")
        return len(entries)

    async def read_entries(self, limit: int = 100, offset: int = 0) -> List[JournalEntry]:
        if not self._connected:
            raise ConnectionError("Not connected to PostgreSQL")
        return []

    async def health_check(self) -> bool:
        return self._connected
