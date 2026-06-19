"""AES-256 encryption/decryption for sensitive configuration values.

The encryption key is read from the ENCRYPTION_KEY environment variable.
If not set, a warning is logged and values are stored/returned as-is (dev mode).
"""

import base64
import hashlib
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_ENCRYPTION_KEY: bytes | None = None

# Config keys whose values are secrets and must be encrypted at rest / masked in responses.
SENSITIVE_KEYS = {
    "api_key", "secret", "password", "token", "secret_key", "access_token",
    "app_secret", "client_secret",
}


def _get_key() -> bytes | None:
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is not None:
        return _ENCRYPTION_KEY
    raw = os.environ.get("ENCRYPTION_KEY")
    if not raw:
        logger.warning("ENCRYPTION_KEY not set – secrets will NOT be encrypted (dev mode)")
        return None
    _ENCRYPTION_KEY = hashlib.sha256(raw.encode()).digest()  # 32 bytes = AES-256
    return _ENCRYPTION_KEY


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext prefixed with 'enc:'."""
    key = _get_key()
    if not key:
        return plaintext
    try:
        from cryptography.fernet import Fernet
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return "enc:" + f.encrypt(plaintext.encode()).decode()
    except ImportError:
        logger.warning("cryptography package not installed, falling back to no-op encryption")
        return plaintext


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a value. If not prefixed with 'enc:', return as-is."""
    if not ciphertext or not ciphertext.startswith("enc:"):
        return ciphertext
    key = _get_key()
    if not key:
        return ciphertext
    try:
        from cryptography.fernet import Fernet
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.decrypt(ciphertext[4:].encode()).decode()
    except Exception:
        logger.error("Failed to decrypt value – returning masked")
        return "***"


def encrypt_config_json(config: dict | None) -> dict | None:
    """Encrypt sensitive keys in a config dict (api_key, secret, password, token)."""
    if not config:
        return config
    result = dict(config)
    for k, v in result.items():
        if k in SENSITIVE_KEYS and isinstance(v, str) and not v.startswith("enc:"):
            result[k] = encrypt_value(v)
    return result


def decrypt_config_json(config: dict | None) -> dict | None:
    """Decrypt sensitive keys in a config dict."""
    if not config:
        return config
    result = dict(config)
    for k, v in result.items():
        if isinstance(v, str) and v.startswith("enc:"):
            result[k] = decrypt_value(v)
    return result


def mask_config_json(config: dict | None) -> dict | None:
    """Return config with sensitive values masked as '***' for API responses."""
    if not config:
        return config
    result = dict(config)
    for k in result:
        if k in SENSITIVE_KEYS:
            result[k] = "***"
    return result
