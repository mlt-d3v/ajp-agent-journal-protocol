"""SHA-256 hash chain with Ed25519 signatures."""
import os
from typing import Optional

from ed25519 import SigningKey

from .entry import JournalEntry


class JournalChain:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.entries: list[JournalEntry] = []
        self.signing_key = SigningKey(os.urandom(32))
        self.verifying_key = self.signing_key.get_verifying_key()

    def append(self, entry: JournalEntry) -> JournalEntry:
        if self.entries:
            entry.parent_hash = self.entries[-1].entry_hash
        entry.compute_hash()
        sig = self.signing_key.sign(
            entry.entry_hash.encode() + entry.agent_id.encode() + str(entry.timestamp).encode()
        )
        entry.signature = sig.hex()
        self.entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        if not self.entries:
            return True
        for i, entry in enumerate(self.entries):
            if i == 0 and entry.parent_hash is not None:
                return False
            if i > 0 and entry.parent_hash != self.entries[i - 1].entry_hash:
                return False
            if not self._verify_signature(entry):
                return False
        return True

    def _verify_signature(self, entry: JournalEntry) -> bool:
        if not entry.signature or not entry.entry_hash:
            return False
        try:
            sig = bytes.fromhex(entry.signature)
            msg = (
                entry.entry_hash.encode()
                + entry.agent_id.encode()
                + str(entry.timestamp).encode()
            )
            return self.verifying_key.verify(sig, msg) is None
        except (ValueError, Exception):
            return False

    def get_head_hash(self) -> Optional[str]:
        if self.entries:
            return self.entries[-1].entry_hash
        return None
