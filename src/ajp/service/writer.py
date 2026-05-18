"""Background batch writer with retry and exponential backoff."""
import asyncio
import logging
from typing import Optional

from .buffer import WriteBuffer
from .storage import StorageBackend

logger = logging.getLogger(__name__)


class BatchWriter:
    def __init__(self, buffer: WriteBuffer, storage: StorageBackend,
                 batch_size: int = 50, flush_interval: float = 2.0):
        self.buffer = buffer
        self.storage = storage
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._write_count = 0
        self._error_count = 0
        self._max_retries = 3
        self._base_backoff = 0.1

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._write_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._drain()

    async def _write_loop(self):
        while self._running:
            try:
                has_entries = await self.buffer.wait_for_entries(timeout=self.flush_interval)
                if has_entries or self.buffer.size() >= self.batch_size:
                    await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Write loop error: {e}")
                await asyncio.sleep(self._base_backoff)

    async def _flush(self):
        batch = await self.buffer.get_batch(max_batch=self.batch_size)
        if not batch:
            return
        retry_count = 0
        while retry_count < self._max_retries:
            try:
                await self.storage.write_batch(batch)
                self._write_count += len(batch)
                return
            except Exception:
                retry_count += 1
                self._error_count += 1
                backoff = self._base_backoff * (2 ** retry_count)
                await asyncio.sleep(backoff)
                await self.buffer.put(*batch)
                batch = []
                continue

    async def _drain(self):
        while self.buffer.size() > 0:
            batch = await self.buffer.get_batch(max_batch=self.batch_size)
            if batch:
                try:
                    await self.storage.write_batch(batch)
                    self._write_count += len(batch)
                except Exception:
                    pass

    @property
    def write_count(self) -> int:
        return self._write_count
