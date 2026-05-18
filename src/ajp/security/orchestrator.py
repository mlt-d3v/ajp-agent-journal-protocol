"""Security orchestrator coordinating Vault, HSM, and Anchoring."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from ..core.anchoring import MerkleAnchoringService
from ..core.entry import JournalEntry
from .hsm import HSMBackend, KeyType, SoftwareHSM
from .vault_client import VaultClient


class AuditEvent(Enum):
    KEY_GENERATED = "key_generated"
    KEY_ROTATED = "key_rotated"
    KEY_DESTROYED = "key_destroyed"
    SIGNATURE_CREATED = "signature_created"
    SIGNATURE_VERIFIED = "signature_verified"
    SECRET_STORED = "secret_stored"
    SECRET_RETRIEVED = "secret_retrieved"
    ROOT_ANCHORED = "root_anchored"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"


@dataclass
class AuditLogEntry:
    event: AuditEvent
    agent_id: str
    timestamp: datetime
    details: dict = field(default_factory=dict)


class SecurityOrchestrator:
    def __init__(self, vault: Optional[VaultClient] = None,
                 hsm: Optional[HSMBackend] = None,
                 anchoring: Optional[MerkleAnchoringService] = None):
        self.vault = vault or VaultClient()
        self.hsm = hsm or SoftwareHSM()
        self.anchoring = anchoring or MerkleAnchoringService()
        self._audit_log: list[AuditLogEntry] = []
        self._agent_keys: dict[str, str] = {}

    def provision_agent(self, agent_id: str) -> bool:
        key_id = f"{agent_id}_signing_key"
        if self.hsm.generate_key(key_id, KeyType.ED25519):
            self._agent_keys[agent_id] = key_id
            self._audit(AuditEvent.KEY_GENERATED, agent_id, {"key_id": key_id})
            if self.vault.is_connected:
                self.vault.write(f"agents/{agent_id}/key_id", {"key_id": key_id})
                self._audit(AuditEvent.SECRET_STORED, agent_id, {"path": f"agents/{agent_id}/key_id"})
            return True
        return False

    def sign_entry(self, agent_id: str, entry: JournalEntry) -> bool:
        key_id = self._agent_keys.get(agent_id)
        if not key_id:
            return False
        if not entry.entry_hash:
            entry.compute_hash()
        data = entry.entry_hash.encode() + agent_id.encode() + str(entry.timestamp).encode()
        sig = self.hsm.sign(key_id, data)
        if sig:
            entry.signature = sig.hex()
            self._audit(AuditEvent.SIGNATURE_CREATED, agent_id, {"entry_hash": entry.entry_hash})
            return True
        return False

    def verify_entry(self, agent_id: str, entry: JournalEntry) -> bool:
        key_id = self._agent_keys.get(agent_id)
        if not key_id:
            return False
        if not entry.signature or not entry.entry_hash:
            return False
        data = entry.entry_hash.encode() + agent_id.encode() + str(entry.timestamp).encode()
        result = self.hsm.verify(key_id, data, bytes.fromhex(entry.signature))
        self._audit(AuditEvent.SIGNATURE_VERIFIED, agent_id, {"valid": result})
        return result

    def rotate_agent_key(self, agent_id: str) -> bool:
        key_id = self._agent_keys.get(agent_id)
        if not key_id:
            return False
        if self.hsm.rotate_key(key_id):
            new_key_id = f"{key_id}_v{self.hsm._keys.get(key_id, {}).get('version', 1)}"
            self._agent_keys[agent_id] = new_key_id
            self._audit(AuditEvent.KEY_ROTATED, agent_id, {"old_key": key_id, "new_key": new_key_id})
            return True
        return False

    def anchor_merkle_root(self, root_hash: str) -> bool:
        record = self.anchoring.anchor_root(root_hash)
        if record:
            self._audit(AuditEvent.ROOT_ANCHORED, "system", {"root": root_hash, "anchor": record.anchor_id})
            return True
        return False

    def get_audit_log(self, event: Optional[AuditEvent] = None) -> list[AuditLogEntry]:
        if event:
            return [e for e in self._audit_log if e.event == event]
        return self._audit_log.copy()

    def _audit(self, event: AuditEvent, agent_id: str, details: Optional[dict] = None):
        self._audit_log.append(AuditLogEntry(
            event=event,
            agent_id=agent_id,
            timestamp=datetime.utcnow(),
            details=details or {},
        ))
