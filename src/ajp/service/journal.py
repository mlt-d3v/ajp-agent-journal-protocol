"""Async journal service with non-blocking writes."""
import asyncio
from dataclasses import dataclass
from typing import Callable, Optional

from ..core.chain import JournalChain
from ..core.entry import JournalEntry
from ..core.rate_limiter import BackpressureLevel, RateLimitConfig, RateLimiter
from .buffer import WriteBuffer
from .storage import MockStorage, StorageBackend
from .writer import BatchWriter


@dataclass
class JournalConfig:
    agent_id: str = "default"
    batch_size: int = 50
    flush_interval: float = 2.0
    buffer_size: int = 500
    rate_limit_config: Optional[RateLimitConfig] = None
    backpressure_thresholds: Optional[dict] = None
    storage_backend: Optional[StorageBackend] = None


class AsyncJournalService:
    def __init__(self, config: Optional[JournalConfig] = None):
        self.config = config or JournalConfig()
        self.chain = JournalChain(self.config.agent_id)
        self.buffer = WriteBuffer(max_size=self.config.buffer_size)
        self.storage = self.config.storage_backend or MockStorage()
        self.writer = BatchWriter(
            buffer=self.buffer,
            storage=self.storage,
            batch_size=self.config.batch_size,
            flush_interval=self.config.flush_interval,
        )
        self.rate_limiter = RateLimiter(self.config.rate_limit_config)
        self._backpressure_callbacks: list[Callable] = []
        self._running = False

    async def start(self):
        self._running = True
        await self.writer.start()

    async def stop(self):
        self._running = False
        await self.writer.stop()

    async def append_entry(self, entry: JournalEntry) -> bool:
        if not self.rate_limiter.allow():
            await self._notify_backpressure(BackpressureLevel.CRITICAL)
            return False
        if self.buffer.is_full():
            pressure = self.buffer.get_pressure_level()
            await self._notify_backpressure(pressure)
            return False
        entry.parent_hash = self.chain.get_head_hash()
        entry.compute_hash()
        sig = self.chain.signing_key.sign(
            entry.entry_hash.encode() + entry.agent_id.encode() + str(entry.timestamp).encode()
        )
        entry.signature = sig.hex()
        self.chain.entries.append(entry)
        await self.buffer.put(entry)
        return True

    def on_backpressure(self, callback: Callable):
        self._backpressure_callbacks.append(callback)

    async def _notify_backpressure(self, level: BackpressureLevel):
        for cb in self._backpressure_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(level)
                else:
                    cb(level)
            except Exception:
                pass

    async def get_entries(self, limit: int = 100) -> list[JournalEntry]:
        return await self.storage.read_entries(limit=limit)

    def verify_chain(self) -> bool:
        return self.chain.verify_chain()

    @property
    def backpressure_level(self) -> BackpressureLevel:
        return self.buffer.get_pressure_level()
