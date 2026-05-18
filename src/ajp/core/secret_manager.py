"""Secret management with Vault backend and RBAC."""
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SecretLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class VaultBackend(ABC):
    @abstractmethod
    def store(self, path: str, data: dict, level: SecretLevel) -> bool:
        pass

    @abstractmethod
    def retrieve(self, path: str) -> Optional[dict]:
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        pass

    @abstractmethod
    def list_keys(self) -> list[str]:
        pass


@dataclass
class MockVaultBackend(VaultBackend):
    _store: dict[str, dict] = field(default_factory=dict)

    def store(self, path: str, data: dict, level: SecretLevel = SecretLevel.MEDIUM) -> bool:
        self._store[path] = {
            "data": data,
            "level": level.value,
            "created_at": datetime.utcnow().isoformat(),
        }
        return True

    def retrieve(self, path: str) -> Optional[dict]:
        entry = self._store.get(path)
        if entry:
            return entry["data"]
        return None

    def delete(self, path: str) -> bool:
        return self._store.pop(path, None) is not None

    def list_keys(self) -> list[str]:
        return list(self._store.keys())


@dataclass
class RBACPolicy:
    agent_id: str
    allowed_paths: list[str] = field(default_factory=list)
    max_level: SecretLevel = SecretLevel.MEDIUM
    token: Optional[str] = None
    expires_at: Optional[datetime] = None


class SecretManager:
    def __init__(self, backend: Optional[VaultBackend] = None):
        self.backend = backend or MockVaultBackend()
        self.policies: dict[str, RBACPolicy] = {}
        self.tokens: dict[str, str] = {}

    def register_agent(self, agent_id: str, max_level: SecretLevel = SecretLevel.MEDIUM,
                       allowed_paths: Optional[list[str]] = None) -> str:
        policy = RBACPolicy(
            agent_id=agent_id,
            max_level=max_level,
            allowed_paths=allowed_paths or ["*"],
        )
        self.policies[agent_id] = policy
        token = hashlib.sha256(f"{agent_id}-{datetime.utcnow().isoformat()}".encode()).hexdigest()[:32]
        self.tokens[token] = agent_id
        policy.token = token
        return token

    def authenticate(self, token: str) -> Optional[str]:
        return self.tokens.get(token)

    def store_secret(self, agent_id: str, path: str, data: dict,
                     level: SecretLevel = SecretLevel.MEDIUM) -> bool:
        policy = self.policies.get(agent_id)
        if not policy:
            return False
        level_order = ["low", "medium", "high", "critical"]
        if level_order.index(level.value) > level_order.index(policy.max_level.value):
            return False
        if "*" not in policy.allowed_paths and path not in policy.allowed_paths:
            return False
        return self.backend.store(path, data, level)

    def retrieve_secret(self, agent_id: str, path: str) -> Optional[dict]:
        policy = self.policies.get(agent_id)
        if not policy:
            return None
        if "*" not in policy.allowed_paths and path not in policy.allowed_paths:
            return None
        return self.backend.retrieve(path)

    def rotate_token(self, agent_id: str) -> Optional[str]:
        policy = self.policies.get(agent_id)
        if not policy:
            return None
        old_token = policy.token
        if old_token in self.tokens:
            del self.tokens[old_token]
        new_token = self.register_agent(
            agent_id, policy.max_level, policy.allowed_paths
        )
        return new_token

    def revoke_agent(self, agent_id: str) -> bool:
        policy = self.policies.get(agent_id)
        if not policy:
            return False
        if policy.token in self.tokens:
            del self.tokens[policy.token]
        del self.policies[agent_id]
        return True
