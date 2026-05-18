"""Real HashiCorp Vault integration for AJP secret management."""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VaultAuthMethod(str, Enum):
    APP_ROLE = "approle"
    KUBERNETES = "kubernetes"
    TOKEN = "token"
    LDAP = "ldap"
    AWS_IAM = "aws_iam"


class VaultEngineVersion(int, Enum):
    V1 = 1
    V2 = 2


@dataclass
class VaultAuthConfig:
    """Configuration for Vault authentication."""
    auth_method: VaultAuthMethod = VaultAuthMethod.TOKEN
    token: str = ""
    app_role_id: str = ""
    app_secret_id: str = ""
    kubernetes_role: str = ""
    kubernetes_token_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    ldap_username: str = ""
    ldap_password: str = ""
    aws_iam_role: str = ""
    aws_access_key: str = ""
    aws_secret_key: str = ""


@dataclass
class VaultConfig:
    """Configuration for HashiCorp Vault connection."""
    url: str = "http://localhost:8200"
    token: str = ""
    auth_config: Optional[VaultAuthConfig] = None
    namespace: str = ""
    verify_tls: bool = True
    cert_path: str = ""
    key_path: str = ""
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    secret_path: str = "secret/data/ajp"
    transit_path: str = "transit/keys/ajp-key"
    auto_renew: bool = True
    renew_interval: int = 300

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RealVaultClient:
    """
    Production HashiCorp Vault client for AJP secret management.

    Features:
    - Multiple auth methods (AppRole, Kubernetes, Token, LDAP, AWS IAM)
    - KV v2 secret engine support
    - Transit engine for encryption/decryption
    - Automatic token renewal
    - TLS verification
    - Retry logic with exponential backoff
    - Mock fallback when hvac is unavailable
    """

    def __init__(self, config: Optional[VaultConfig] = None):
        self.config = config or VaultConfig()
        self._client = None
        self._is_connected = False
        self._token_ttl = 0
        self._auth_time = 0
        self._secrets_store = {}
        self._transit_keys = {}
        self._write_count = 0
        self._read_count = 0

    async def connect(self) -> bool:
        """Connect to Vault and authenticate."""
        try:
            import hvac
            self._client = hvac.Client(
                url=self.config.url,
                token=self.config.token,
                verify=self.config.verify_tls,
                timeout=self.config.timeout,
            )
            if self.config.namespace:
                self._client.session.headers["X-Vault-Namespace"] = self.config.namespace

            await self._authenticate()
            self._is_connected = True
            logger.info(f"Connected to Vault at {self.config.url}")
            return True
        except ImportError:
            logger.warning("hvac not installed - using mock Vault mode")
            self._is_connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Vault: {e}")
            self._is_connected = False
            return False

    async def _authenticate(self) -> bool:
        """Authenticate with Vault using configured method."""
        auth_config = self.config.auth_config or VaultAuthConfig()

        try:
            if self._client:
                if auth_config.auth_method == VaultAuthMethod.APP_ROLE:
                    return await self._auth_app_role(auth_config)
                elif auth_config.auth_method == VaultAuthMethod.KUBERNETES:
                    return await self._auth_kubernetes(auth_config)
                elif auth_config.auth_method == VaultAuthMethod.LDAP:
                    return await self._auth_ldap(auth_config)
                elif auth_config.auth_method == VaultAuthMethod.AWS_IAM:
                    return await self._auth_aws_iam(auth_config)
                else:
                    # Token auth - verify token
                    self._client.auth.token.lookup_self()
                    self._auth_time = time.time()
                    return True
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    async def _auth_app_role(self, auth_config: VaultAuthConfig) -> bool:
        """Authenticate using AppRole."""
        try:
            if self._client:
                response = self._client.auth.approle.login(
                    role_id=auth_config.app_role_id,
                    secret_id=auth_config.app_secret_id,
                )
                self._client.token = response["auth"]["client_token"]
                self._token_ttl = response["auth"]["lease_duration"]
                self._auth_time = time.time()
                return True
            return True
        except Exception as e:
            logger.error(f"AppRole auth failed: {e}")
            return False

    async def _auth_kubernetes(self, auth_config: VaultAuthConfig) -> bool:
        """Authenticate using Kubernetes service account."""
        try:
            if self._client:
                with open(auth_config.kubernetes_token_path, "r") as f:
                    k8s_token = f.read().strip()

                response = self._client.auth.kubernetes.login(
                    role=auth_config.kubernetes_role,
                    jwt=k8s_token,
                )
                self._client.token = response["auth"]["client_token"]
                self._token_ttl = response["auth"]["lease_duration"]
                self._auth_time = time.time()
                return True
            return True
        except Exception as e:
            logger.error(f"Kubernetes auth failed: {e}")
            return False

    async def _auth_ldap(self, auth_config: VaultAuthConfig) -> bool:
        """Authenticate using LDAP."""
        try:
            if self._client:
                response = self._client.auth.ldap.login(
                    username=auth_config.ldap_username,
                    password=auth_config.ldap_password,
                )
                self._client.token = response["auth"]["client_token"]
                self._token_ttl = response["auth"]["lease_duration"]
                self._auth_time = time.time()
                return True
            return True
        except Exception as e:
            logger.error(f"LDAP auth failed: {e}")
            return False

    async def _auth_aws_iam(self, auth_config: VaultAuthConfig) -> bool:
        """Authenticate using AWS IAM."""
        try:
            if self._client:
                response = self._client.auth.aws_iam.login(
                    role=auth_config.aws_iam_role,
                    access_key=auth_config.aws_access_key,
                    secret_key=auth_config.aws_secret_key,
                )
                self._client.token = response["auth"]["client_token"]
                self._token_ttl = response["auth"]["lease_duration"]
                self._auth_time = time.time()
                return True
            return True
        except Exception as e:
            logger.error(f"AWS IAM auth failed: {e}")
            return False

    async def write_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """Write a secret to Vault KV v2 engine."""
        full_path = f"{self.config.secret_path}/{path}"

        try:
            if self._client:
                for attempt in range(self.config.retry_attempts):
                    try:
                        self._client.secrets.kv_v2.create_or_update_secret(
                            path=full_path,
                            secret=data,
                        )
                        self._write_count += 1
                        return True
                    except Exception as e:
                        logger.error(f"Secret write attempt {attempt + 1} failed: {e}")
                        if attempt < self.config.retry_attempts - 1:
                            await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                        else:
                            raise
            else:
                self._secrets_store[full_path] = {
                    "data": data,
                    "version": 1,
                    "created_time": time.time(),
                }
                self._write_count += 1
                return True
        except Exception as e:
            logger.error(f"Failed to write secret to {full_path}: {e}")
            return False
        return False

    async def read_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """Read a secret from Vault KV v2 engine."""
        full_path = f"{self.config.secret_path}/{path}"

        try:
            if self._client:
                response = self._client.secrets.kv_v2.read_secret_version(path=full_path)
                self._read_count += 1
                return response["data"]["data"]
            else:
                secret = self._secrets_store.get(full_path)
                if secret:
                    self._read_count += 1
                    return secret["data"]
                return None
        except Exception as e:
            logger.error(f"Failed to read secret from {full_path}: {e}")
            return None

    async def delete_secret(self, path: str) -> bool:
        """Delete a secret from Vault."""
        full_path = f"{self.config.secret_path}/{path}"

        try:
            if self._client:
                self._client.secrets.kv_v2.delete_metadata_version(path=full_path)
                return True
            else:
                if full_path in self._secrets_store:
                    del self._secrets_store[full_path]
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete secret from {full_path}: {e}")
            return False

    async def list_secrets(self, path: str = "") -> List[str]:
        """List secrets in a path."""
        full_path = f"{self.config.secret_path}/{path}"

        try:
            if self._client:
                response = self._client.secrets.kv_v2.list_secrets(path=full_path)
                return [s["key"] for s in response.get("data", {}).get("keys", [])]
            else:
                keys = []
                for store_key in self._secrets_store:
                    if store_key.startswith(full_path):
                        relative = store_key[len(full_path):].lstrip("/")
                        if "/" in relative:
                            keys.append(relative.split("/")[0])
                        else:
                            keys.append(relative)
                return list(set(keys))
        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []

    async def encrypt_data(self, plaintext: str) -> Optional[str]:
        """Encrypt data using Vault Transit engine."""
        try:
            if self._client:
                response = self._client.secrets.transit.encrypt_data(
                    name=self.config.transit_path,
                    plaintext=plaintext,
                )
                return response["data"]["ciphertext"]
            else:
                import base64
                cipher = base64.b64encode(plaintext.encode()).decode()
                self._transit_keys[cipher] = plaintext
                return f"vault:v2:{cipher}"
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return None

    async def decrypt_data(self, ciphertext: str) -> Optional[str]:
        """Decrypt data using Vault Transit engine."""
        try:
            if self._client:
                response = self._client.secrets.transit.decrypt_data(
                    name=self.config.transit_path,
                    ciphertext=ciphertext,
                )
                return response["data"]["plaintext"]
            else:
                if ciphertext in self._transit_keys:
                    return self._transit_keys[ciphertext]
                import base64
                clean = ciphertext.replace("vault:v2:", "")
                return base64.b64decode(clean).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None

    async def generate_dynamic_db_creds(self, role_name: str) -> Optional[Dict[str, str]]:
        """Generate dynamic database credentials."""
        try:
            if self._client:
                response = self._client.secrets.database.generate_credentials(role_name)
                return {
                    "username": response["data"]["username"],
                    "password": response["data"]["password"],
                    "lease_id": response["lease_id"],
                    "ttl": response["lease_duration"],
                }
            else:
                import secrets
                return {
                    "username": f"ajp-dynamic-{secrets.token_hex(4)}",
                    "password": secrets.token_hex(16),
                    "lease_id": f"database/{role_name}/{secrets.token_hex(8)}",
                    "ttl": "1h",
                }
        except Exception as e:
            logger.error(f"Failed to generate dynamic credentials: {e}")
            return None

    async def renew_token(self) -> bool:
        """Renew the Vault token."""
        try:
            if self._client:
                self._client.auth.token.renew_self()
                self._auth_time = time.time()
                return True
            return True
        except Exception as e:
            logger.error(f"Token renewal failed: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get Vault client statistics."""
        return {
            "connected": self._is_connected,
            "url": self.config.url,
            "auth_time": self._auth_time,
            "token_ttl": self._token_ttl,
            "write_count": self._write_count,
            "read_count": self._read_count,
            "secrets_stored": len(self._secrets_store),
        }

    async def close(self) -> None:
        """Close the Vault client."""
        if self._client:
            self._client = None
        self._is_connected = False
        logger.info("Vault client closed")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def write_count(self) -> int:
        return self._write_count

    @property
    def read_count(self) -> int:
        return self._read_count
