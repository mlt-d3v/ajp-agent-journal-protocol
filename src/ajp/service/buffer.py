"""In-memory write buffer with priority ordering."""
import asyncio
import heapq
from dataclasses import dataclass, field

from ..core.entry import EventType, JournalEntry
from ..core.rate_limiter import BackpressureLevel


@dataclass(order=True)
class PriorityEntry:
    priority: int
    entry: JournalEntry = field(compare=False)


_EVENT_PRIORITY = {
    EventType.ERROR: 0,
    EventType.COMMIT: 1,
    EventType.SYSTEM: 2,
    EventType.ACTION: 3,
    EventType.OBSERVATION: 4,
    EventType.THOUGHT: 5,
}


class WriteBuffer:
    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self._heap: list[PriorityEntry] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()

    async def put(self, entry: JournalEntry):
        async with self._lock:
            priority = _EVENT_PRIORITY.get(entry.event_type, 5)
            heapq.heappush(self._heap, PriorityEntry(priority, entry))
            self._not_empty.set()

    async def get_batch(self, max_batch: int = 50) -> list[JournalEntry]:
        async with self._lock:
            batch = []
            for _ in range(min(max_batch, len(self._heap))):
                if self._heap:
                    item = heapq.heappop(self._heap)
                    batch.append(item.entry)
            if not self._heap:
                self._not_empty.clear()
            return batch

    async def wait_for_entries(self, timeout: float = 1.0) -> bool:
        try:
            await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def is_full(self) -> bool:
        return len(self._heap) >= self.max_size

    def size(self) -> int:
        return len(self._heap)

    def get_pressure_level(self) -> BackpressureLevel:
        utilization = len(self._heap) / self.max_size
        if utilization >= 0.95:
            return BackpressureLevel.CRITICAL
        if utilization >= 0.8:
            return BackpressureLevel.HIGH
        if utilization >= 0.5:
            return BackpressureLevel.MEDIUM
        if utilization >= 0.2:
            return BackpressureLevel.LOW
        return BackpressureLevel.OK
