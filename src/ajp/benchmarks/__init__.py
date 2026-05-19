"""
AJP Phase 9: Performance Benchmark Suite

Benchmarks for throughput, latency, scale, and memory usage
across all core AJP operations.
"""

import time
import os
import statistics
import gc
import json
from dataclasses import dataclass, field, asdict
from typing import Callable, Any
from datetime import datetime, timezone


# ──────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────


@dataclass
class BenchmarkResult:
    name: str
    ops: int
    elapsed: float
    throughput: float  # ops/sec
    latency_p50: float  # ms
    latency_p95: float
    latency_p99: float
    memory_delta_mb: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def ops_per_sec(self) -> str:
        return f"{self.throughput:,.0f}"


@dataclass
class BenchmarkSuiteResult:
    timestamp: str
    python_version: str
    platform: str
    results: list[BenchmarkResult] = field(default_factory=list)

    def add(self, result: BenchmarkResult) -> None:
        self.results.append(result)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "python_version": self.python_version,
            "platform": self.platform,
            "results": [asdict(r) for r in self.results],
        }


# ──────────────────────────────────────────────
# Benchmark harness
# ──────────────────────────────────────────────


class Benchmark:
    """Simple benchmark harness — no external deps needed."""

    def __init__(self, warmup: int = 10):
        self.warmup = warmup

    def measure(
        self,
        name: str,
        fn: Callable[[], Any],
        iterations: int = 1000,
        metadata: dict = None,  # type: ignore[assignment]
    ) -> BenchmarkResult:
        metadata = metadata or {}
        # Warmup
        for _ in range(self.warmup):
            fn()

        # Measure memory before
        gc.collect()
        mem_before = _get_memory_mb()

        # Timed runs
        latencies: list[float] = []
        start = time.perf_counter()
        for _ in range(iterations):
            t0 = time.perf_counter()
            fn()
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000)  # ms
        elapsed = time.perf_counter() - start

        # Memory after
        gc.collect()
        mem_after = _get_memory_mb()

        latencies.sort()
        return BenchmarkResult(
            name=name,
            ops=iterations,
            elapsed=elapsed,
            throughput=iterations / elapsed,
            latency_p50=_percentile(latencies, 50),
            latency_p95=_percentile(latencies, 95),
            latency_p99=_percentile(latencies, 99),
            memory_delta_mb=mem_after - mem_before,
            metadata=metadata or {},
        )


# ──────────────────────────────────────────────
# Report generation
# ──────────────────────────────────────────────


def generate_text_report(suite: BenchmarkSuiteResult) -> str:
    lines = [
        "=" * 72,
        f"AJP Performance Benchmark Report",
        f"Generated: {suite.timestamp}",
        f"Python:    {suite.python_version}",
        f"Platform:  {suite.platform}",
        "=" * 72,
        "",
        f"{'Operation':<40} {'Ops':>8} {'Throughput':>12} {'P50(ms)':>10} {'P95(ms)':>10} {'P99(ms)':>10} {'Mem(MB)':>8}",
        "-" * 98,
    ]

    for r in suite.results:
        lines.append(
            f"{r.name:<40} {r.ops:>8,} {r.ops_per_sec:>12} {r.latency_p50:>10.2f} {r.latency_p95:>10.2f} {r.latency_p99:>10.2f} {r.memory_delta_mb:>+8.1f}"
        )

    lines.extend([
        "",
        "-" * 98,
        f"Total benchmarks: {len(suite.results)}",
        "",
    ])

    return "\n".join(lines)


def generate_json_report(suite: BenchmarkSuiteResult) -> str:
    return json.dumps(suite.to_dict(), indent=2, default=str)


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────


def _get_memory_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    k = (len(data) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(data):
        return data[-1]
    return data[f] + (k - f) * (data[c] - data[f])
