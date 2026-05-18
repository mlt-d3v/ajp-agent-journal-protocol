"""Rate limiting with token bucket and circuit breaker."""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BackpressureLevel(Enum):
    OK = "ok"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RateLimitConfig:
    requests_per_second: float = 10.0
    burst_size: int = 20
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 30.0
    backpressure_thresholds: dict = field(
        default_factory=lambda: {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 0.95}
    )


class RateLimiter:
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._tokens = self.config.burst_size
        self._last_refill = time.monotonic()
        self._error_count = 0
        self._last_error = 0.0
        self._circuit_open = False

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.config.burst_size,
            self._tokens + elapsed * self.config.requests_per_second,
        )
        self._last_refill = now

    def allow(self) -> bool:
        if self._circuit_open:
            if time.monotonic() - self._last_error > self.config.circuit_breaker_timeout:
                self._circuit_open = False
                self._error_count = 0
                self._tokens = self.config.burst_size
            else:
                return False
        self._refill()
        if self._tokens < 1:
            self._record_error()
            return False
        self._tokens -= 1
        return True

    def _record_error(self):
        self._error_count += 1
        self._last_error = time.monotonic()
        if self._error_count >= self.config.circuit_breaker_threshold:
            self._circuit_open = True

    def get_backpressure(self) -> BackpressureLevel:
        utilization = 1.0 - (self._tokens / self.config.burst_size)
        thresholds = self.config.backpressure_thresholds
        if utilization >= thresholds["critical"]:
            return BackpressureLevel.CRITICAL
        if utilization >= thresholds["high"]:
            return BackpressureLevel.HIGH
        if utilization >= thresholds["medium"]:
            return BackpressureLevel.MEDIUM
        if utilization >= thresholds["low"]:
            return BackpressureLevel.LOW
        return BackpressureLevel.OK


class CircuitBreaker:
    def __init__(self, threshold: int = 5, timeout: float = 30.0):
        self.threshold = threshold
        self.timeout = timeout
        self._failure_count = 0
        self._last_failure = 0.0
        self._state = "closed"

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            if time.monotonic() - self._last_failure > self.timeout:
                self._state = "half-open"
                return False
            return True
        return False

    def record_success(self):
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self):
        self._failure_count += 1
        self._last_failure = time.monotonic()
        if self._failure_count >= self.threshold:
            self._state = "open"

    def allow(self) -> bool:
        return not self.is_open
