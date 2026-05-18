"""Failure interceptor agent for detecting and remediating failure patterns."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from ..core.entry import EventType, JournalEntry


class FailurePattern(Enum):
    REPEATED_ERRORS = "repeated_errors"
    CASCADING_FAILURE = "cascading_failure"
    INJECTION_ATTEMPT = "injection_attempt"
    ANOMALY_SPIKE = "anomaly_spike"
    STALE_AGENT = "stale_agent"
    RATE_LIMIT_EXHAUSTED = "rate_limit_exhausted"
    CHAIN_TAMPER = "chain_tamper"


class RemediationAction(Enum):
    THROTTLE = "throttle"
    QUARANTINE = "quarantine"
    CIRCUIT_BREAK = "circuit_break"
    KEY_ROTATE = "key_rotate"
    ALERT = "alert"
    NONE = "none"


@dataclass
class FailureAlert:
    pattern: FailurePattern
    agent_id: str
    severity: str
    description: str
    remediation: RemediationAction
    timestamp: datetime = field(default_factory=datetime.utcnow)
    count: int = 0


class FailureInterceptor:
    def __init__(self, error_threshold: int = 5, stale_threshold: int = 300):
        self.error_threshold = error_threshold
        self.stale_threshold = stale_threshold
        self._error_counts: dict[str, int] = {}
        self._last_activity: dict[str, datetime] = {}
        self._alerts: list[FailureAlert] = []
        self._remediated: dict[str, RemediationAction] = {}

    def check_entry(self, entry: JournalEntry) -> Optional[FailureAlert]:
        self._last_activity[entry.agent_id] = entry.timestamp
        if entry.event_type == EventType.ERROR:
            self._error_counts[entry.agent_id] = self._error_counts.get(entry.agent_id, 0) + 1
            if self._error_counts[entry.agent_id] >= self.error_threshold:
                alert = FailureAlert(
                    pattern=FailurePattern.REPEATED_ERRORS,
                    agent_id=entry.agent_id,
                    severity="high",
                    description=f"Agent {entry.agent_id} exceeded error threshold",
                    remediation=RemediationAction.THROTTLE,
                    count=self._error_counts[entry.agent_id],
                )
                self._alerts.append(alert)
                self._remediated[entry.agent_id] = RemediationAction.THROTTLE
                return alert
        entry_data_str = str(entry.entry_data).lower()
        injection_keywords = ["ignore previous", "system prompt", "override", "disregard"]
        if any(kw in entry_data_str for kw in injection_keywords):
            alert = FailureAlert(
                pattern=FailurePattern.INJECTION_ATTEMPT,
                agent_id=entry.agent_id,
                severity="critical",
                description="Potential prompt injection detected",
                remediation=RemediationAction.QUARANTINE,
            )
            self._alerts.append(alert)
            self._remediated[entry.agent_id] = RemediationAction.QUARANTINE
            return alert
        return None

    def check_stale_agents(self) -> list[FailureAlert]:
        alerts = []
        now = datetime.utcnow()
        for agent_id, last_active in self._last_activity.items():
            if (now - last_active).seconds > self.stale_threshold:
                alert = FailureAlert(
                    pattern=FailurePattern.STALE_AGENT,
                    agent_id=agent_id,
                    severity="medium",
                    description=f"Agent {agent_id} inactive for {(now - last_active).seconds}s",
                    remediation=RemediationAction.ALERT,
                )
                self._alerts.append(alert)
                alerts.append(alert)
        return alerts

    def get_alerts(self, agent_id: Optional[str] = None) -> list[FailureAlert]:
        if agent_id:
            return [a for a in self._alerts if a.agent_id == agent_id]
        return self._alerts.copy()

    def is_remediated(self, agent_id: str) -> Optional[RemediationAction]:
        return self._remediated.get(agent_id)

    def clear_alerts(self, agent_id: Optional[str] = None):
        if agent_id:
            self._alerts = [a for a in self._alerts if a.agent_id != agent_id]
            self._remediated.pop(agent_id, None)
            self._error_counts.pop(agent_id, None)
        else:
            self._alerts.clear()
            self._remediated.clear()
            self._error_counts.clear()
