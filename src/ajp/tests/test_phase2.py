"""Phase 2 tests - Async Journal Service."""
import asyncio
import sys
import unittest

sys.path.insert(0, "/Users/michaelthomas/.hermes/skills/ajp-agent-journal-protocol/src")

from ajp.core.entry import EventType, JournalEntry
from ajp.core.rate_limiter import BackpressureLevel
from ajp.service.buffer import WriteBuffer
from ajp.service.journal import AsyncJournalService, JournalConfig
from ajp.service.storage import MockStorage
from ajp.service.writer import BatchWriter


class TestWriteBuffer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        self.buffer = WriteBuffer(max_size=100)

    async def test_put_and_get(self):
        entry = JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={"msg": "test"})
        await self.buffer.put(entry)
        self.assertEqual(self.buffer.size(), 1)
        batch = await self.buffer.get_batch()
        self.assertEqual(len(batch), 1)

    async def test_priority_ordering(self):
        error = JournalEntry(agent_id="a", event_type=EventType.ERROR, entry_data={"msg": "err"})
        thought = JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={"msg": "think"})
        await self.buffer.put(thought)
        await self.buffer.put(error)
        batch = await self.buffer.get_batch()
        self.assertEqual(batch[0].event_type, EventType.ERROR)

    async def test_is_full(self):
        small = WriteBuffer(max_size=2)
        await small.put(JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={}))
        await small.put(JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={}))
        self.assertTrue(small.is_full())

    async def test_pressure_levels(self):
        buf = WriteBuffer(max_size=100)
        self.assertEqual(buf.get_pressure_level(), BackpressureLevel.OK)
        for i in range(25):
            await buf.put(JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={"i": i}))
        self.assertEqual(buf.get_pressure_level(), BackpressureLevel.LOW)

    async def test_wait_for_entries(self):
        buf = WriteBuffer()
        self.assertFalse(await buf.wait_for_entries(timeout=0.1))
        await buf.put(JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={}))
        self.assertTrue(await buf.wait_for_entries(timeout=0.1))


class TestMockStorage(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        self.storage = MockStorage()

    async def test_write_and_read(self):
        entries = [JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={"msg": "test"})]
        await self.storage.write_batch(entries)
        result = await self.storage.read_entries()
        self.assertEqual(len(result), 1)

    async def test_health_check(self):
        self.assertTrue(await self.storage.health_check())

    async def test_write_count(self):
        entries = [JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={"i": i}) for i in range(10)]
        await self.storage.write_batch(entries)
        self.assertEqual(self.storage.write_count, 10)


class TestAsyncJournalService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        self.storage = MockStorage()
        config = JournalConfig(agent_id="test_agent", batch_size=10, flush_interval=0.5, storage_backend=self.storage)
        self.service = AsyncJournalService(config)
        await self.service.start()

    async def asyncTearDown(self):
        await self.service.stop()

    async def test_append_entry(self):
        entry = JournalEntry(agent_id="test_agent", event_type=EventType.THOUGHT, entry_data={"msg": "hello"})
        result = await self.service.append_entry(entry)
        self.assertTrue(result)

    async def test_chain_verification(self):
        for i in range(5):
            entry = JournalEntry(agent_id="test_agent", event_type=EventType.THOUGHT, entry_data={"i": i})
            await self.service.append_entry(entry)
        self.assertTrue(self.service.verify_chain())

    async def test_backpressure_rejection(self):
        small_config = JournalConfig(agent_id="test", buffer_size=2, batch_size=100, flush_interval=10.0)
        small_service = AsyncJournalService(small_config)
        await small_service.start()
        await small_service.append_entry(JournalEntry(agent_id="test", event_type=EventType.THOUGHT, entry_data={}))
        await small_service.append_entry(JournalEntry(agent_id="test", event_type=EventType.THOUGHT, entry_data={}))
        result = await small_service.append_entry(JournalEntry(agent_id="test", event_type=EventType.THOUGHT, entry_data={}))
        await small_service.stop()
        self.assertFalse(result)

    async def test_entries_persisted(self):
        for i in range(10):
            entry = JournalEntry(agent_id="test_agent", event_type=EventType.THOUGHT, entry_data={"i": i})
            await self.service.append_entry(entry)
        await asyncio.sleep(1.0)
        stored = await self.service.get_entries(limit=100)
        self.assertEqual(len(stored), 10)


class TestBatchWriter(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        self.storage = MockStorage()
        self.buffer = WriteBuffer(max_size=500)
        self.writer = BatchWriter(buffer=self.buffer, storage=self.storage, batch_size=10, flush_interval=0.3)

    async def test_write_loop(self):
        await self.writer.start()
        for i in range(20):
            await self.buffer.put(JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={"i": i}))
        await asyncio.sleep(1.0)
        await self.writer.stop()
        stored = await self.storage.read_entries()
        self.assertEqual(len(stored), 20)

    async def test_drain_on_stop(self):
        await self.writer.start()
        for i in range(5):
            await self.buffer.put(JournalEntry(agent_id="a", event_type=EventType.THOUGHT, entry_data={"i": i}))
        await self.writer.stop()
        stored = await self.storage.read_entries()
        self.assertEqual(len(stored), 5)


if __name__ == "__main__":
    unittest.main()
