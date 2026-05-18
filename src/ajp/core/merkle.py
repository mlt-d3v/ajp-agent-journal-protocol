"""Merkle tree for batch verification."""
import hashlib
from typing import Optional

from .entry import JournalEntry


class MerkleTree:
    def __init__(self):
        self.leaves: list[str] = []
        self.root: Optional[str] = None

    def add_entry(self, entry: JournalEntry) -> str:
        if not entry.entry_hash:
            entry.compute_hash()
        self.leaves.append(entry.entry_hash)
        self._build()
        return entry.entry_hash

    def _build(self):
        if not self.leaves:
            self.root = None
            return
        level = self.leaves[:]
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]
                parent = hashlib.sha256((left + right).encode()).hexdigest()
                next_level.append(parent)
            level = next_level
        self.root = level[0] if level else None

    def verify(self, entry_hash: str) -> bool:
        return entry_hash in self.leaves

    def get_proof(self, entry_hash: str) -> Optional[list[str]]:
        if entry_hash not in self.leaves:
            return None
        proof = []
        level = self.leaves[:]
        target = entry_hash
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]
                if left == target or right == target:
                    proof.append(left if left != target else right)
                parent = hashlib.sha256((left + right).encode()).hexdigest()
                next_level.append(parent)
            level = next_level
            target = parent
        return proof
