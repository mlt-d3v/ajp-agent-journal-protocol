# ajp/core/data_retention.py
"""
Data Retention Manager responsible for masking PII data points
to ensure compliance (GDPR, CCPA, etc.) when logs are processed.
Should be injected with a storage adapter (e.g., a MockDBAdapter)
to isolate persistence logic from the core PII logic.
"""
import re
from typing import Any, Dict

class DataRetentionManager:
    """Manages the masking of sensitive data."""
    
    def __init__(self, storage_adapter=None):
        self.storage_adapter = storage_adapter
        self.log("DataRetentionManager initialized. Using mock adapter.")

    def _mask_value(self, value: Any) -> Any:
        """Applies consistent masking logic to types."""
        if isinstance(value, str):
            if 'email' in value:
                # Basic email masking
                return f"masked_email<{value.rsplit('@')[-1]}>"
            if 'phone' in value:
                # Basic phone number masking
                return "xxx-xxx-####"
            if 'ssn' in value or 'id' in value.lower():
                # Assume IDs/SSNs are sensitive
                return "###-##-####"
        return value

    def mask_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively masks PII across all dictionary values."""
        masked_data = {}
        for key, value in data.items():
            if isinstance(value, dict):
                masked_data[key] = self.mask_pii(value) # Recurse
            else:
                masked_data[key] = self._mask_value(value)
        return masked_data

    def log(self, message: str):
        """Placeholder for internal logging / debugging info."""
        print(f"[AJP-DRM] {message}")

# Example usage (for testing):
# print(DataRetentionManager().mask_pii({"name": "Alice", "email": "alice@corp.com", "ssn": "123-45-6789"}))