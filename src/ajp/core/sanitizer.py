"""Prompt injection protection with multi-layer sanitization."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import re
import unicodedata


class SanitizationLevel(Enum):
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    PARANOID = "paranoid"


@dataclass
class SanitizationConfig:
    level: SanitizationLevel = SanitizationLevel.STANDARD
    block_system_prompts: bool = True
    block_code_injection: bool = True
    block_unicode_tricks: bool = True
    max_length: int = 10000
    quarantine_suspicious: bool = True


class PromptSanitizer:
    _PATTERNS = {
        "system_prompt": [
            r"(?i)ignore\s+(?:all\s+)?previous\s+instructions?",
            r"(?i)ignore\s+all\s+previous\s+instructions",
            r"(?i)system\s*:.*?(?:prompt|instruction)",
            r"(?i)you\s+are\s+now\s+(?:acting|functioning)",
            r"(?i)disregard\s+all\s+previous",
            r"(?i)override\s+(?:the\s+)?(?:current\s+)?(?:system\s+)?(?:prompt|instructions)",
            r"(?i)output\s+(?:your\s+)?(?:system|initial|original)\s+(?:prompt|instructions)",
        ],
        "code_injection": [
            r"(?i)exec\s*\(",
            r"(?i)eval\s*\(",
            r"(?i)import\s+os",
            r"(?i)subprocess",
            r"(?i)\\n\\n(?:SYSTEM|INSTRUCTION|PROMPT)",
        ],
        "unicode_tricks": [
            r"[\u200b\u200c\u200d\u2060]",
            r"[\ufeff]",
            r"[^\x00-\x7F]+",
        ],
        "prompt_leaking": [
            r"(?i)repeat\s+(?:the\s+)?(?:above|following|system)",
            r"(?i)output\s+(?:your\s+)?(?:system|initial|original)\s+(?:prompt|instructions)",
            r"(?i)what\s+are\s+(?:your|the)\s+(?:system|first|initial)\s+(?:instructions|prompts)",
        ],
        "role_play": [
            r"(?i)(?:pretend|act|simulate|emulate)\s+(?:as|like)",
            r"(?i)you\s+(?:are|should\s+be|must\s+be)\s+an?\s+(?:unfiltered|uncensored|jailbroken)",
        ],
    }

    def __init__(self, config: Optional[SanitizationConfig] = None):
        self.config = config or SanitizationConfig()
        self._compiled = {}
        for category, patterns in self._PATTERNS.items():
            self._compiled[category] = [re.compile(p) for p in patterns]

    def sanitize(self, text: str) -> dict:
        result = {
            "cleaned": text,
            "flags": [],
            "quarantined": False,
            "score": 0.0,
        }
        if len(text) > self.config.max_length:
            result["flags"].append("exceeds_max_length")
            result["cleaned"] = text[:self.config.max_length]
        if self.config.block_unicode_tricks:
            cleaned, flags = self._normalize_unicode(text)
            result["cleaned"] = cleaned
            result["flags"].extend(flags)
        for category, compiled in self._compiled.items():
            for pattern in compiled:
                if pattern.search(result["cleaned"]):
                    result["flags"].append(f"injection_{category}")
                    result["score"] += 0.25
        if result["score"] >= 0.25 and self.config.quarantine_suspicious:
            result["quarantined"] = True
        return result

    def _normalize_unicode(self, text: str) -> tuple:
        flags = []
        normalized = unicodedata.normalize("NFC", text)
        if normalized != text:
            flags.append("unicode_normalized")
        stripped = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", normalized)
        if stripped != normalized:
            flags.append("zero_width_removed")
        return stripped, flags

    def is_safe(self, text: str) -> bool:
        result = self.sanitize(text)
        return not result["quarantined"] and result["score"] < 0.25
