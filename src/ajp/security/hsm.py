"""HSM (Hardware Security Module) backend interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import hashlib
import os


class KeyType(Enum):
    ED25519 = "ed25519"
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"
    EC_P256 = "ec_p256"


class KeyState(Enum):
    ACTIVE = "active"
    ROTATED = "rotated"
    DESTROYED = "destroyed"


@dataclass
class HSMBackend(ABC):
    @abstractmethod
    def generate_key(self, key_id: str, key_type: KeyType) -> bool:
        pass

    @abstractmethod
    def sign(self, key_id: str, data: bytes) -> Optional[bytes]:
        pass

    @abstractmethod
    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        pass

    @abstractmethod
    def rotate_key(self, key_id: str) -> bool:
        pass

    @abstractmethod
    def destroy_key(self, key_id: str) -> bool:
        pass

    @abstractmethod
    def get_key_state(self, key_id: str) -> Optional[KeyState]:
        pass


@dataclass
class SoftwareHSM(HSMBackend):
    _keys: Dict[str, dict] = field(default_factory=dict)

    def generate_key(self, key_id: str, key_type: KeyType = KeyType.ED25519) -> bool:
        self._keys[key_id] = {
            "type": key_type.value,
            "state": KeyState.ACTIVE,
            "private": os.urandom(32),
            "public": hashlib.sha256(os.urandom(32)).hexdigest(),
            "version": 1,
        }
        return True

    def sign(self, key_id: str, data: bytes) -> Optional[bytes]:
        key = self._keys.get(key_id)
        if not key or key["state"] != KeyState.ACTIVE:
            return None
        return hashlib.sha256(key["private"] + data).digest()

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        key = self._keys.get(key_id)
        if not key or key["state"] != KeyState.ACTIVE:
            return False
        expected = hashlib.sha256(key["private"] + data).digest()
        return expected == signature

    def rotate_key(self, key_id: str) -> bool:
        key = self._keys.get(key_id)
        if not key:
            return False
        key["state"] = KeyState.ROTATED
        self._keys[f"{key_id}_v{key['version'] + 1}"] = {
            "type": key["type"],
            "state": KeyState.ACTIVE,
            "private": os.urandom(32),
            "public": hashlib.sha256(os.urandom(32)).hexdigest(),
            "version": key["version"] + 1,
        }
        return True

    def destroy_key(self, key_id: str) -> bool:
        key = self._keys.get(key_id)
        if not key:
            return False
        key["state"] = KeyState.DESTROYED
        key["private"] = b""
        return True

    def get_key_state(self, key_id: str) -> Optional[KeyState]:
        key = self._keys.get(key_id)
        return key["state"] if key else None


class CloudHSM(SoftwareHSM):
    def __init__(self, provider: str = "aws", region: str = "us-east-1"):
        self.provider = provider
        self.region = region
        super().__init__()
