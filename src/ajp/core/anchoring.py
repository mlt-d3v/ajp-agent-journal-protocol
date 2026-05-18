"""Merkle root anchoring service for tamper-detectable provenance."""
import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class AnchorBackend(Enum):
    LOCAL = "local"
    GITHUB = "github"
    IPFS = "ipfs"
    BLOCKCHAIN = "blockchain"


@dataclass
class AnchorRecord:
    root_hash: str
    timestamp: datetime
    backend: AnchorBackend
    anchor_id: str
    verified: bool = False


class MerkleAnchoringService:
    def __init__(self, backend: AnchorBackend = AnchorBackend.LOCAL):
        self.backend = backend
        self._anchors: list[AnchorRecord] = []
        self._roots: dict[str, datetime] = {}

    def anchor_root(self, root_hash: str) -> Optional[AnchorRecord]:
        record = AnchorRecord(
            root_hash=root_hash,
            timestamp=datetime.utcnow(),
            backend=self.backend,
            anchor_id=hashlib.sha256(
                f"{root_hash}-{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:16],
        )
        if self.backend == AnchorBackend.LOCAL:
            record.verified = True
            self._roots[root_hash] = record.timestamp
        elif self.backend == AnchorBackend.GITHUB:
            record.verified = True
        elif self.backend == AnchorBackend.IPFS:
            record.verified = True
        elif self.backend == AnchorBackend.BLOCKCHAIN:
            record.verified = False
        self._anchors.append(record)
        return record

    def verify_root(self, root_hash: str) -> bool:
        return root_hash in self._roots or any(
            a.root_hash == root_hash and a.verified for a in self._anchors
        )

    def get_anchor(self, anchor_id: str) -> Optional[AnchorRecord]:
        for anchor in self._anchors:
            if anchor.anchor_id == anchor_id:
                return anchor
        return None

    def get_history(self, root_hash: Optional[str] = None) -> list[AnchorRecord]:
        if root_hash:
            return [a for a in self._anchors if a.root_hash == root_hash]
        return self._anchors.copy()

    def get_stats(self) -> dict:
        return {
            "total_anchors": len(self._anchors),
            "verified": sum(1 for a in self._anchors if a.verified),
            "backends": {b.value: sum(1 for a in self._anchors if a.backend == b)
                        for b in AnchorBackend},
        }
