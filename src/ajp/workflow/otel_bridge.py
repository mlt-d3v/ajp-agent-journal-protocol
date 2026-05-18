"""OpenTelemetry bridge for distributed tracing across agent nodes."""
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class SpanKind(Enum):
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(Enum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


@dataclass
class SpanAttribute:
    key: str
    value: Any
    type: str = "string"


@dataclass
class SpanEvent:
    name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str = ""
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    attributes: list[SpanAttribute] = field(default_factory=list)
    events: list[SpanEvent] = field(default_factory=list)
    resource: dict[str, str] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        if self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def is_root(self) -> bool:
        return self.parent_span_id is None

    def add_attribute(self, key: str, value: Any, type: str = "string"):
        self.attributes.append(SpanAttribute(key=key, value=value, type=type))

    def add_event(self, name: str, attributes: Optional[dict] = None):
        self.events.append(SpanEvent(name=name, attributes=attributes or {}))

    def set_status(self, status: SpanStatus, description: Optional[str] = None):
        self.status = status
        if description:
            self.add_attribute("status.description", description)

    def end(self):
        self.end_time = time.monotonic()

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "status": self.status.value,
            "duration": self.duration,
            "attributes": [{"key": a.key, "value": a.value} for a in self.attributes],
            "events": [{"name": e.name, "timestamp": e.timestamp.isoformat()} for e in self.events],
        }


class Tracer:
    def __init__(self, service_name: str = "ajp-agent"):
        self.service_name = service_name
        self._spans: dict[str, Span] = {}
        self._traces: dict[str, list[str]] = {}
        self._active_span: Optional[Span] = None

    def _generate_id(self, length: int = 16) -> str:
        return hashlib.sha256(f"{time.monotonic()}-{id(self)}".encode()).hexdigest()[:length]

    def start_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL,
                   resource: Optional[dict] = None) -> Span:
        trace_id = self._generate_id()
        span_id = self._generate_id()
        parent_span_id = self._active_span.span_id if self._active_span else None
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            resource=resource or {"service.name": self.service_name},
        )
        self._spans[span_id] = span
        if trace_id not in self._traces:
            self._traces[trace_id] = []
        self._traces[trace_id].append(span_id)
        self._active_span = span
        return span

    def end_span(self, span_id: Optional[str] = None):
        span = self._spans.get(span_id or (self._active_span.span_id if self._active_span else ""))
        if span:
            span.end()
            if self._active_span and self._active_span.span_id == span_id:
                parent_id = span.parent_span_id
                self._active_span = self._spans.get(parent_id) if parent_id else None

    def create_child_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL) -> Optional[Span]:
        if not self._active_span:
            return None
        child_trace_id = self._active_span.trace_id
        child_span_id = self._generate_id()
        child = Span(
            trace_id=child_trace_id,
            span_id=child_span_id,
            parent_span_id=self._active_span.span_id,
            name=name,
            kind=kind,
            resource=self._active_span.resource,
        )
        self._spans[child_span_id] = child
        self._traces[child_trace_id].append(child_span_id)
        self._active_span = child
        return child

    def get_span(self, span_id: str) -> Optional[Span]:
        return self._spans.get(span_id)

    def get_trace(self, trace_id: str) -> list[Span]:
        span_ids = self._traces.get(trace_id, [])
        return [self._spans[sid] for sid in span_ids if sid in self._spans]

    def export_spans(self, trace_id: Optional[str] = None) -> list[dict]:
        if trace_id:
            spans = self.get_trace(trace_id)
        else:
            spans = list(self._spans.values())
        return [s.to_dict() for s in spans]

    def get_stats(self) -> dict:
        completed = sum(1 for s in self._spans.values() if s.end_time)
        errored = sum(1 for s in self._spans.values() if s.status == SpanStatus.ERROR)
        return {
            "total_spans": len(self._spans),
            "total_traces": len(self._traces),
            "completed": completed,
            "errored": errored,
            "active": len(self._spans) - completed,
        }


class MetricsExporter:
    def __init__(self):
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[dict] = None):
        key = self._label_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: Optional[dict] = None):
        key = self._label_key(name, labels)
        self._gauges[key] = value

    def record_histogram(self, name: str, value: float, labels: Optional[dict] = None):
        key = self._label_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def _label_key(self, name: str, labels: Optional[dict] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"

    def get_counter(self, name: str, labels: Optional[dict] = None) -> float:
        return self._counters.get(self._label_key(name, labels), 0.0)

    def get_gauge(self, name: str, labels: Optional[dict] = None) -> float:
        return self._gauges.get(self._label_key(name, labels), 0.0)

    def get_histogram_stats(self, name: str, labels: Optional[dict] = None) -> dict:
        values = self._histograms.get(self._label_key(name, labels), [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "sum": 0}
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "sum": sum(values),
        }

    def export_all(self) -> dict:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: {"count": len(v), "mean": sum(v)/len(v) if v else 0}
                          for k, v in self._histograms.items()},
        }
