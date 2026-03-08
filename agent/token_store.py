"""Secure token loader — tries encrypted file first, falls back to plaintext."""

import json
import os
import getpass
import stat

TOKENS_FILE = os.path.join(os.path.dirname(__file__), "access_tokens.json")
ENCRYPTED_FILE = os.path.join(os.path.dirname(__file__), "access_tokens.enc")
SALT_FILE = os.path.join(os.path.dirname(__file__), ".token_salt")


def load_tokens(password: str = None) -> dict:
    """Load access tokens, preferring encrypted file.

    If encrypted file exists, prompts for password (or uses provided one).
    Falls back to plaintext JSON if no encrypted file.
    """
    # Try encrypted first
    if os.path.exists(ENCRYPTED_FILE) and os.path.exists(SALT_FILE):
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64

            if password is None:
                password = getpass.getpass("Token decryption password: ")

            with open(SALT_FILE, "rb") as f:
                salt = f.read()

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480_000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            fernet = Fernet(key)

            with open(ENCRYPTED_FILE, "rb") as f:
                encrypted = f.read()

            decrypted = fernet.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            raise ValueError(f"Failed to decrypt tokens: {e}")

    # Fall back to plaintext
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r") as f:
            return json.load(f)

    raise FileNotFoundError(
        "No access tokens found. Run notebook 01 to connect accounts."
    )


def save_tokens(tokens: dict):
    """Save tokens to plaintext file with restricted permissions."""
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    os.chmod(TOKENS_FILE, stat.S_IRUSR | stat.S_IWUSR)
