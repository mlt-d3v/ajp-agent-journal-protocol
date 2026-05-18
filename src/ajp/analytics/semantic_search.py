"""Semantic search over journal entries using vector similarity."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import hashlib
import json
import math


@dataclass
class SearchResult:
    entry_hash: str
    agent_id: str
    score: float
    timestamp: datetime
    entry_data: dict


class SemanticSearchEngine:
    def __init__(self):
        self._index: Dict[str, dict] = {}
        self._embeddings: Dict[str, List[float]] = {}

    def _hash_embed(self, text: str) -> List[float]:
        dims = 16
        result = []
        for i in range(dims):
            h = hashlib.sha256(f"{text}-{i}".encode()).hexdigest()
            result.append(int(h[:8], 16) / 0xFFFFFFFF)
        return result

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def index_entry(self, entry_hash: str, agent_id: str, content: str,
                   timestamp: datetime, entry_data: dict):
        embedding = self._hash_embed(content)
        self._index[entry_hash] = {
            "agent_id": agent_id,
            "timestamp": timestamp,
            "entry_data": entry_data,
        }
        self._embeddings[entry_hash] = embedding

    def search(self, query: str, agent_id: Optional[str] = None,
               limit: int = 10, min_score: float = 0.0) -> List[SearchResult]:
        query_embedding = self._hash_embed(query)
        results = []
        for entry_hash, embedding in self._embeddings.items():
            idx = self._index[entry_hash]
            if agent_id and idx["agent_id"] != agent_id:
                continue
            score = self._cosine_similarity(query_embedding, embedding)
            if score >= min_score:
                results.append(SearchResult(
                    entry_hash=entry_hash,
                    agent_id=idx["agent_id"],
                    score=score,
                    timestamp=idx["timestamp"],
                    entry_data=idx["entry_data"],
                ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def get_stats(self) -> dict:
        return {"indexed": len(self._index), "embeddings": len(self._embeddings)}
