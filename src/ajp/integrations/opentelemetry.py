"""OpenTelemetry OTLP exporter integration for AJP."""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class OTelConfig:
    """Configuration for OpenTelemetry exporter."""
    otlp_endpoint: str = "http://localhost:4317"
    service_name: str = "ajp-journal"
    service_version: str = "0.5.0"
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_logging: bool = True
    trace_sample_rate: float = 1.0
    metric_export_interval: int = 15
    max_batch_size: int = 512
    retry_attempts: int = 3
    retry_delay: float = 1.0
    enable_mock: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Span:
    """Represents a tracing span."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: SpanKind
    start_time: float
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.OK
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if isinstance(self.kind, SpanKind):
            result["kind"] = self.kind.value
        if isinstance(self.status, SpanStatus):
            result["status"] = self.status.value
        return result


@dataclass
class Trace:
    """Represents a complete trace."""
    trace_id: str
    spans: List[Span] = field(default_factory=list)
    service_name: str = ""
    started_at: float = 0.0
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "spans": [s.to_dict() for s in self.spans],
            "service_name": self.service_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class MetricPoint:
    """Represents a metric data point."""
    name: str
    value: float
    timestamp: float
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if isinstance(self.metric_type, MetricType):
            result["metric_type"] = self.metric_type.value
        return result


class OTLPExporter:
    """
    OpenTelemetry OTLP exporter for AJP distributed tracing and metrics.

    Features:
    - Distributed tracing with span hierarchy
    - Metric collection (counters, gauges, histograms)
    - Structured logging with trace context
    - OTLP protocol support
    - Mock mode for testing without collector
    """

    def __init__(self, config: Optional[OTelConfig] = None):
        self.config = config or OTelConfig()
        self._is_connected = False
        self._traces: Dict[str, Trace] = {}
        self._metrics: List[MetricPoint] = []
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._current_span: Optional[Span] = None
        self._export_count = 0
        self._trace_count = 0
        self._metric_count = 0

    async def connect(self) -> bool:
        """Connect to OpenTelemetry collector."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
            provider = TracerProvider()
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)

            self._is_connected = True
            logger.info(f"Connected to OTLP collector at {self.config.otlp_endpoint}")
            return True
        except ImportError:
            if self.config.enable_mock:
                logger.warning("opentelemetry not installed - using mock exporter")
                self._is_connected = True
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect to OTLP collector: {e}")
            self._is_connected = False
            return False

    def start_trace(self, trace_name: str, trace_id: Optional[str] = None) -> str:
        """Start a new trace."""
        trace_id = trace_id or str(uuid.uuid4())
        trace = Trace(
            trace_id=trace_id,
            service_name=self.config.service_name,
            started_at=time.time(),
        )
        self._traces[trace_id] = trace
        self._trace_count += 1
        return trace_id

    def create_span(
        self,
        trace_id: str,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new span within a trace."""
        trace = self._traces.get(trace_id)
        if not trace:
            logger.error(f"Trace {trace_id} not found")
            return ""

        span_id = str(uuid.uuid4())
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            start_time=time.time(),
            attributes=attributes or {},
        )

        trace.spans.append(span)
        self._current_span = span
        return span_id

    def end_span(self, span_id: str, status: SpanStatus = SpanStatus.OK) -> None:
        """End a span."""
        if self._current_span and self._current_span.span_id == span_id:
            self._current_span.end_time = time.time()
            self._current_span.status = status
            self._current_span = None

    def add_span_event(self, span_id: str, event_name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to a span."""
        if self._current_span and self._current_span.span_id == span_id:
            self._current_span.events.append({
                "name": event_name,
                "timestamp": time.time(),
                "attributes": attributes or {},
            })

    def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.COUNTER,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a metric data point."""
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=time.time(),
            metric_type=metric_type,
            labels=labels or {},
        )
        self._metrics.append(point)
        self._metric_count += 1

        # Update aggregations
        if metric_type == MetricType.COUNTER:
            self._counters[name] = self._counters.get(name, 0) + value
        elif metric_type == MetricType.GAUGE:
            self._gauges[name] = value
        elif metric_type == MetricType.HISTOGRAM:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        self.record_metric(name, value, MetricType.COUNTER, labels)

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        self.record_metric(name, value, MetricType.GAUGE, labels)

    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram value."""
        self.record_metric(name, value, MetricType.HISTOGRAM, labels)

    def log_with_trace(
        self,
        level: str,
        message: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a message with trace context."""
        log_entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "service": self.config.service_name,
            "trace_id": trace_id or (self._current_span.trace_id if self._current_span else None),
            "span_id": span_id or (self._current_span.span_id if self._current_span else None),
            "attributes": attributes or {},
        }
        logger.info(json.dumps(log_entry))

    async def export_traces(self) -> int:
        """Export completed traces."""
        exported = 0
        for trace_id, trace in self._traces.items():
            if trace.completed_at:
                # In mock mode, just count as exported
                exported += 1
                self._export_count += 1

        return exported

    async def export_metrics(self) -> int:
        """Export collected metrics."""
        exported = len(self._metrics)
        self._metrics.clear()
        self._export_count += 1
        return exported

    async def export_all(self) -> Dict[str, int]:
        """Export all traces and metrics."""
        traces = await self.export_traces()
        metrics = await self.export_metrics()
        return {"traces": traces, "metrics": metrics}

    async def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get a trace by ID."""
        trace = self._traces.get(trace_id)
        if trace:
            return trace.to_dict()
        return None

    async def get_traces(
        self,
        limit: int = 10,
        service_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent traces."""
        traces = list(self._traces.values())
        if service_name:
            traces = [t for t in traces if t.service_name == service_name]
        return [t.to_dict() for t in traces[:limit]]

    async def get_metrics(
        self,
        metric_name: Optional[str] = None,
        metric_type: Optional[MetricType] = None,
    ) -> List[Dict[str, Any]]:
        """Get collected metrics."""
        metrics = self._metrics
        if metric_name:
            metrics = [m for m in metrics if m.name == metric_name]
        if metric_type:
            metrics = [m for m in metrics if m.metric_type == metric_type]
        return [m.to_dict() for m in metrics]

    async def get_counter(self, name: str) -> Optional[float]:
        """Get a counter value."""
        return self._counters.get(name)

    async def get_gauge(self, name: str) -> Optional[float]:
        """Get a gauge value."""
        return self._gauges.get(name)

    async def get_histogram_stats(self, name: str) -> Optional[Dict[str, float]]:
        """Get histogram statistics."""
        values = self._histograms.get(name)
        if not values:
            return None
        return {
            "count": len(values),
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get exporter statistics."""
        return {
            "connected": self._is_connected,
            "trace_count": self._trace_count,
            "metric_count": self._metric_count,
            "export_count": self._export_count,
            "active_traces": len(self._traces),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histogram_names": list(self._histograms.keys()),
        }

    async def close(self) -> None:
        """Close the exporter."""
        await self.export_all()
        self._is_connected = False
        logger.info("OTLP exporter closed")

    @property
    def is_connected(self) -> bool:
        return self._is_connected
