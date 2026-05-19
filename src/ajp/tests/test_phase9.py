"""
Phase 9 Tests: Performance Benchmarks

Measures throughput, latency, and memory for all core AJP operations.
Run with: python -m pytest src/ajp/tests/test_phase9.py -v
"""

import pytest
import sys
import os

from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ajp.core.entry import JournalEntry, EventType
from ajp.core.chain import JournalChain
from ajp.core.merkle import MerkleTree
from ajp.analytics.semantic_search import SemanticSearchEngine
from ajp.benchmarks import Benchmark, BenchmarkSuiteResult
from ajp.benchmarks import generate_text_report, generate_json_report


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def benchmark() -> Benchmark:
    return Benchmark(warmup=5)


@pytest.fixture
def sample_entry() -> JournalEntry:
    return JournalEntry(
        agent_id="bench-agent",
        event_type=EventType.THOUGHT,
        entry_data={"task": "benchmark_test", "value": 42},
    )


@pytest.fixture
def journal_chain() -> JournalChain:
    return JournalChain("bench-agent")


# ──────────────────────────────────────────────
# Individual benchmarks
# ──────────────────────────────────────────────


def test_benchmark_journal_entry_creation(benchmark, sample_entry):
    """Throughput for creating JournalEntry instances."""
    result = benchmark.measure(
        "JournalEntry creation",
        lambda: JournalEntry(
            agent_id="bench-agent",
            event_type=EventType.THOUGHT,
            entry_data={"data": "x" * 100},
        ),
        iterations=5000,
    )
    assert result.throughput > 100, f"Too slow: {result.throughput:.0f} ops/sec"


def test_benchmark_entry_hashing(benchmark, sample_entry):
    """Throughput for computing entry hashes."""
    entry = JournalEntry(
        agent_id="bench-agent",
        event_type=EventType.THOUGHT,
        entry_data={"data": "x" * 200},
    )
    result = benchmark.measure(
        "Entry hash computation",
        lambda: entry.compute_hash(),
        iterations=2000,
    )
    assert result.throughput > 50, f"Too slow: {result.throughput:.0f} ops/sec"


def test_benchmark_chain_append(benchmark, journal_chain):
    """Throughput for appending entries to the journal chain."""
    entries = [
        JournalEntry(
            agent_id="bench-agent",
            event_type=EventType.THOUGHT,
            entry_data={"seq": i},
        )
        for i in range(100)
    ]
    idx = [0]

    def append_one():
        journal_chain.append(entries[idx[0] % len(entries)])
        idx[0] += 1

    result = benchmark.measure(
        "Chain append",
        append_one,
        iterations=500,
    )
    assert result.throughput > 10, f"Too slow: {result.throughput:.0f} ops/sec"


def test_benchmark_chain_verify(benchmark, journal_chain):
    """Latency for verifying a chain of 100 entries."""
    for i in range(100):
        entry = JournalEntry(
            agent_id="bench-agent",
            event_type=EventType.THOUGHT,
            entry_data={"seq": i},
        )
        journal_chain.append(entry)

    result = benchmark.measure(
        "Chain verify (100 entries)",
        lambda: journal_chain.verify_chain(),
        iterations=200,
    )
    # Must complete in under 500ms
    assert result.latency_p99 < 500, f"Chain verify too slow: {result.latency_p99:.1f}ms"


def test_benchmark_chain_verify_large(benchmark):
    """Latency for verifying a chain of 1000 entries."""
    chain = JournalChain("bench-large")
    for i in range(1000):
        entry = JournalEntry(
            agent_id="bench-large",
            event_type=EventType.THOUGHT,
            entry_data={"seq": i},
        )
        chain.append(entry)

    result = benchmark.measure(
        "Chain verify (1000 entries)",
        lambda: chain.verify_chain(),
        iterations=50,
    )
    # Must complete in under 2 seconds
    assert result.latency_p99 < 2000, f"Large chain verify too slow: {result.latency_p99:.1f}ms"


def test_benchmark_merkle_tree_add(benchmark):
    """Throughput for adding entries to a Merkle tree."""
    tree = MerkleTree()
    entries = [
        JournalEntry(
            agent_id="bench-agent",
            event_type=EventType.THOUGHT,
            entry_data={"seq": i},
        )
        for i in range(200)
    ]
    for e in entries:
        e.entry_hash = e.compute_hash()

    idx = [0]

    def add_one():
        tree.add_entry(entries[idx[0] % len(entries)])
        idx[0] += 1

    result = benchmark.measure(
        "Merkle tree add entry",
        add_one,
        iterations=500,
    )
    assert result.throughput > 50, f"Too slow: {result.throughput:.0f} ops/sec"


def test_benchmark_merkle_tree_proof(benchmark):
    """Latency for generating Merkle proofs."""
    tree = MerkleTree()
    entries = []
    for i in range(100):
        e = JournalEntry(
            agent_id="bench-agent",
            event_type=EventType.THOUGHT,
            entry_data={"seq": i},
        )
        e.entry_hash = e.compute_hash()
        tree.add_entry(e)
        entries.append(e)

    target_hash = entries[50].entry_hash

    result = benchmark.measure(
        "Merkle proof generation",
        lambda: tree.get_proof(target_hash),
        iterations=200,
    )
    assert result.latency_p99 < 100, f"Proof gen too slow: {result.latency_p99:.1f}ms"


def test_benchmark_semantic_search(benchmark):
    """Throughput for semantic search indexing and query."""
    engine = SemanticSearchEngine()
    for i in range(50):
        engine.index_entry(
            entry_hash=f"hash-{i}",
            agent_id="bench-agent",
            content=f"test content number {i} with some meaningful words",
            timestamp=datetime.now(timezone.utc),
            entry_data={"seq": i},
        )

    result = benchmark.measure(
        "Semantic search query",
        lambda: engine.search("meaningful test"),
        iterations=200,
    )
    assert result.latency_p99 < 200, f"Search too slow: {result.latency_p99:.1f}ms"


# ──────────────────────────────────────────────
# Full suite run
# ──────────────────────────────────────────────


@pytest.mark.slow
def test_full_benchmark_suite(benchmark, tmp_path):
    """Run all benchmarks and generate a report file."""
    suite = BenchmarkSuiteResult(
        timestamp=__import__("datetime").datetime.now().isoformat(),
        python_version=sys.version,
        platform=sys.platform,
    )

    # JournalEntry creation
    suite.add(benchmark.measure(
        "JournalEntry creation (batch)",
        lambda: JournalEntry(
            agent_id="suite-agent",
            event_type=EventType.THOUGHT,
            entry_data={"data": "x" * 100},
        ),
        iterations=2000,
    ))

    # Hash computation
    entry = JournalEntry(agent_id="suite-agent", event_type=EventType.THOUGHT, entry_data={"x": 1})
    suite.add(benchmark.measure(
        "Hash computation",
        lambda: entry.compute_hash(),
        iterations=2000,
    ))

    # Chain operations
    chain = JournalChain("suite-agent")
    for i in range(100):
        e = JournalEntry(agent_id="suite-agent", event_type=EventType.THOUGHT, entry_data={"seq": i})
        chain.append(e)
    suite.add(benchmark.measure(
        "Chain verify (100 entries)",
        lambda: chain.verify_chain(),
        iterations=100,
    ))

    # Generate reports
    text_report = generate_text_report(suite)
    json_report = generate_json_report(suite)

    report_path = tmp_path / "benchmark-report.txt"
    report_path.write_text(text_report)
    json_path = tmp_path / "benchmark-report.json"
    json_path.write_text(json_report)

    print(f"\n\nBenchmark report saved to {report_path}")
    print(text_report)

    assert len(suite.results) == 3
