"""Ops console for real-time monitoring and alerting."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from ..core.entry import EventType, JournalEntry
from ..core.rate_limiter import BackpressureLevel


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    name: str
    metric: str
    threshold: float
    severity: AlertSeverity
    check_fn: Optional[Callable] = None


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: dict[str, str] = field(default_factory=dict)


class OpsConsole:
    def __init__(self):
        self._metrics: dict[str, list[MetricPoint]] = {}
        self._alert_rules: list[AlertRule] = []
        self._alerts: list[dict] = []
        self._error_count = 0
        self._total_count = 0
        self._backpressure_level = BackpressureLevel.OK
        self._storage_utilization = 0.0

    def record_metric(self, name: str, value: float, labels: Optional[dict] = None):
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(MetricPoint(name=name, value=value, labels=labels or {}))

    def record_entry(self, entry: JournalEntry):
        self._total_count += 1
        self.record_metric("entries_total", self._total_count, {"agent": entry.agent_id})
        if entry.event_type == EventType.ERROR:
            self._error_count += 1
            self.record_metric("errors_total", self._error_count, {"agent": entry.agent_id})

    def set_backpressure(self, level: BackpressureLevel):
        self._backpressure_level = level
        self.record_metric("backpressure_level", self._backpressure_level.ordinal if hasattr(self._backpressure_level, 'ordinal') else 0)

    def set_storage_utilization(self, utilization: float):
        self._storage_utilization = utilization
        self.record_metric("storage_utilization", utilization)

    def get_health_status(self) -> HealthStatus:
        error_rate = self._error_count / max(self._total_count, 1)
        if error_rate > 0.3 or self._backpressure_level == BackpressureLevel.CRITICAL:
            return HealthStatus.UNHEALTHY
        if error_rate > 0.1 or self._backpressure_level in (BackpressureLevel.HIGH, BackpressureLevel.MEDIUM):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def add_alert_rule(self, rule: AlertRule):
        self._alert_rules.append(rule)

    def check_alerts(self) -> list[dict]:
        new_alerts = []
        error_rate = self._error_count / max(self._total_count, 1)
        if error_rate > 0.2:
            alert = {
                "name": "high_error_rate",
                "severity": AlertSeverity.WARNING.value,
                "value": error_rate,
                "timestamp": datetime.utcnow().isoformat(),
            }
            new_alerts.append(alert)
            self._alerts.append(alert)
        if self._storage_utilization > 0.9:
            alert = {
                "name": "storage_critical",
                "severity": AlertSeverity.CRITICAL.value,
                "value": self._storage_utilization,
                "timestamp": datetime.utcnow().isoformat(),
            }
            new_alerts.append(alert)
            self._alerts.append(alert)
        for rule in self._alert_rules:
            if rule.check_fn:
                try:
                    if rule.check_fn():
                        alert = {
                            "name": rule.name,
                            "severity": rule.severity.value,
                            "value": rule.threshold,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        new_alerts.append(alert)
                        self._alerts.append(alert)
                except Exception:
                    pass
        return new_alerts

    def get_metrics(self, name: Optional[str] = None, limit: int = 100) -> dict[str, list[MetricPoint]]:
        if name:
            return {name: self._metrics.get(name, [])[-limit:]}
        return {k: v[-limit:] for k, v in self._metrics.items()}

    def export_prometheus(self) -> str:
        lines = []
        for name, points in self._metrics.items():
            if points:
                latest = points[-1]
                labels = ",".join(f'{k}="{v}"' for k, v in latest.labels.items())
                if labels:
                    lines.append(f"{name}{{{labels}}} {latest.value}")
                else:
                    lines.append(f"{name} {latest.value}")
        return "\n".join(lines)

    def get_stats(self) -> dict:
        return {
            "total_entries": self._total_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._total_count, 1),
            "health": self.get_health_status().value,
            "backpressure": self._backpressure_level.value,
            "storage_utilization": self._storage_utilization,
            "alert_count": len(self._alerts),
        }
