"""
OroGest Lex — Encryption Service (Fase 13)
AES-256-GCM encryption for sensitive data at rest.

Used for: client names, case notes, document content flagged as confidential.
NOT used for: search indexes, metadata, non-sensitive fields.

Compliance: Ley 25.326 (Protección de Datos Personales Argentina)
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

settings = get_settings()

# Derive a proper 32-byte key from the config value
_raw_key = settings.ENCRYPTION_KEY.encode("utf-8")
if len(_raw_key) < 32:
    # Pad with SHA-256 if key is too short (dev only — production should use proper 32-byte key)
    import hashlib

    _key = hashlib.sha256(_raw_key).digest()
else:
    _key = _raw_key[:32]


def encrypt_field(plaintext: str) -> str:
    """
    Encrypt a string field with AES-256-GCM.
    Returns: base64-encoded string of nonce + ciphertext + tag.
    """
    if not plaintext:
        return plaintext

    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Combine: nonce (12 bytes) + ciphertext+tag
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode("utf-8")


def decrypt_field(encrypted: str) -> str:
    """
    Decrypt a base64-encoded AES-256-GCM field.
    Returns: plaintext string.
    """
    if not encrypted:
        return encrypted

    combined = base64.b64decode(encrypted.encode("utf-8"))
    nonce = combined[:12]
    ciphertext = combined[12:]

    aesgcm = AESGCM(_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def is_encrypted(value: str) -> bool:
    """Check if a value looks like it's already encrypted (base64 + min length)."""
    if not value or len(value) < 24:
        return False
    try:
        decoded = base64.b64decode(value)
        return len(decoded) > 12  # At least nonce + some ciphertext
    except Exception:  # noqa: BLE001 — best-effort format sniff, not a security decision: any decode failure means "not encrypted"
        return False
