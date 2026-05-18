"""Data retention management with tiering and GDPR compliance."""
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class RetentionTier(Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class RetentionConfig:
    hot_days: int = 30
    warm_days: int = 90
    cold_days: int = 365
    archive_days: int = 1825
    pii_fields: list[str] = field(default_factory=lambda: ["email", "phone", "name", "address"])
    mask_char: str = "*"


class DataRetentionManager:
    _PII_PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    }

    def __init__(self, config: Optional[RetentionConfig] = None):
        self.config = config or RetentionConfig()
        self._entries: dict[str, dict] = {}
        self._audit_log: list[dict] = []

    def _get_tier(self, age_days: int) -> RetentionTier:
        if age_days <= self.config.hot_days:
            return RetentionTier.HOT
        if age_days <= self.config.warm_days:
            return RetentionTier.WARM
        if age_days <= self.config.cold_days:
            return RetentionTier.COLD
        if age_days <= self.config.archive_days:
            return RetentionTier.ARCHIVED
        return RetentionTier.DELETED

    def add_entry(self, entry_id: str, data: dict, timestamp: Optional[datetime] = None):
        ts = timestamp or datetime.utcnow()
        self._entries[entry_id] = {
            "data": data,
            "timestamp": ts,
            "tier": RetentionTier.HOT,
            "shredded": False,
        }

    def get_entry(self, entry_id: str) -> Optional[dict]:
        entry = self._entries.get(entry_id)
        if not entry:
            return None
        age = (datetime.utcnow() - entry["timestamp"]).days
        new_tier = self._get_tier(age)
        if new_tier == RetentionTier.DELETED:
            self._audit_log.append({
                "action": "auto_delete",
                "entry_id": entry_id,
                "timestamp": datetime.utcnow().isoformat(),
            })
            del self._entries[entry_id]
            return None
        if new_tier != entry["tier"]:
            entry["tier"] = new_tier
        return entry["data"]

    def mask_pii(self, data: dict) -> dict:
        result = dict(data)
        for key, value in result.items():
            if isinstance(value, str):
                if key.lower() in self.config.pii_fields:
                    result[key] = self.config.mask_char * len(value)
                for _pattern_name, pattern in self._PII_PATTERNS.items():
                    matches = re.findall(pattern, value)
                    if matches:
                        for match in matches:
                            value = value.replace(match, self.config.mask_char * len(match))
                        result[key] = value
        return result

    def shred_entry(self, entry_id: str) -> bool:
        entry = self._entries.pop(entry_id, None)
        if not entry:
            return False
        entry["shredded"] = True
        self._audit_log.append({
            "action": "gdpr_shred",
            "entry_id": entry_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return True

    def get_audit_log(self) -> list[dict]:
        return self._audit_log.copy()

    def get_stats(self) -> dict:
        tiers = {t.value: 0 for t in RetentionTier}
        for entry in self._entries.values():
            tiers[entry["tier"].value] += 1
        return {"total": len(self._entries), "tiers": tiers}
