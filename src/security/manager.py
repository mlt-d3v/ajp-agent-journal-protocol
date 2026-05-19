# ajp/security/manager.py
"""
Secret Management component responsible for securely storing, retrieving,
and auditing sensitive credentials.
Must utilize an abstract StorageAdapter to decouple from actual backend (e.g., Vault, AWS Secrets Manager).
"""
from typing import Dict, Any, Optional
import abc

class ISecretStore(abc.ABC):
    """Interface for any secret storage mechanism."""
    
    @abc.abstractmethod
    def connect(self, config: Dict[str, Any]) -> bool:
        """Initializes the connection to the secret store."""
        pass

    @abc.abstractmethod
    def store(self, key_id: str, secret_data: Dict[str, Any], access_level: str) -> bool:
        """Stores a secret, checking permissions based on access_level."""
        pass

    @abc.abstractmethod
    def retrieve(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a secret by ID."""
        pass

class MemorySecretStore(ISecretStore):
    """
    Mock implementation of ISecretStore for unit testing and development.
    Uses a simple in-memory dictionary.
    WARNING: Data is lost on process exit. NEVER use in production.
    """
    def __init__(self):
        self._store: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def connect(self, config: Dict[str, Any]) -> bool:
        """Mock connection success."""
        print("[AJP-SM] Successfully initialized MemorySecretStore.")
        return True

    def store(self, key_id: str, secret_data: Dict[str, Any], access_level: str) -> bool:
        """Stores mock secret."""
        self._store[(key_id, access_level)] = secret_data
        print(f"[AJP-SM (MOCK)] Stored secret for {key_id} at '{access_level}' level.")
        return True

    def retrieve(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves mock secret."""
        # Simple retrieval: checks for existence regardless of access_level, for mock simplicity.
        for (k, l), v in self._store.items():
            if k == key_id:
                return v
        return None

def retrieve_secret(store: ISecretStore, key_id: str) -> Optional[Dict[str, Any]]:
    """High-level wrapper function to retrieve secrets."""
    return store.retrieve(key_id)

class SecretManager:
    """
    High-level service manager. Wraps the ISecretStore adapter to provide 
    a consistent, usage-friendly API for the agent.
    """
    def __init__(self, store: Optional[ISecretStore] = None):
        # Default to the mock adapter if none is provided
        self.store: ISecretStore = store if store else MemorySecretStore()
        self.store.connect(config={}) # Simulate connection

    def store_secret(self, key_id: str, secret_data: Dict[str, Any], access_level: str) -> bool:
        return self.store.store(key_id, secret_data, access_level)

    def retrieve_secret(self, key_id: str) -> Optional[Dict[str, Any]]:
        return self.store.retrieve(key_id)

# Example usage (for testing):
# sm = SecretManager()
# print(sm.store_secret("test", {"token": "xyz"}, "high"))
# print(sm.retrieve_secret("test"))