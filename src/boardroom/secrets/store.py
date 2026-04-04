from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_KEYRING_SERVICE = "boardroom"
_KEYRING_USER = "fernet_master"
_ENV_MASTER_KEY = "BOARDROOM_CREDENTIAL_KEY"


class CredentialStoreError(RuntimeError):
    """Raised when encrypted credential storage cannot be read or written safely."""


def _fernet_key_from_env() -> bytes | None:
    raw = os.environ.get(_ENV_MASTER_KEY, "").strip()
    if not raw:
        return None
    try:
        key = raw.encode("ascii")
    except UnicodeEncodeError:
        return None
    try:
        Fernet(key)
    except (ValueError, TypeError):
        raise CredentialStoreError(
            f"{_ENV_MASTER_KEY} must be a valid Fernet key (url-safe base64).",
        ) from None
    return key


class CredentialStore:
    """Encrypt provider API keys at rest.

    When ``base_dir`` is omitted, the wrapping key is stored in the OS secret
    service (keyring) when available, not next to ``credentials.json``. For tests
    or custom locations, pass ``base_dir`` to keep the key file alongside the
    JSON store. Set ``BOARDROOM_CREDENTIAL_KEY`` to a Fernet key to override
    both (advanced / headless).
    """

    def __init__(self, *, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or (Path.home() / ".boardroom")
        self._explicit_base = base_dir is not None
        self._key_path = self._base_dir / "credentials.key"
        self._store_path = self._base_dir / "credentials.json"

    def set(self, provider: str, api_key: str) -> None:
        key = api_key.strip()
        if not key:
            raise CredentialStoreError("API key cannot be empty.")
        fernet = Fernet(self._load_or_create_master_key())
        payload = self._read_store_file()
        payload[provider] = fernet.encrypt(key.encode("utf-8")).decode("utf-8")
        self._write_store_file(payload)

    def get(self, provider: str) -> str | None:
        if not self._store_path.exists():
            return None
        mk = self._read_master_key()
        if mk is None:
            return None
        payload = self._read_store_file()
        encrypted = payload.get(provider)
        if encrypted is None:
            return None
        try:
            return Fernet(mk).decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise CredentialStoreError(
                "Stored credentials are unreadable or corrupted.") from exc

    def has(self, provider: str) -> bool:
        return self.get(provider) is not None

    def _load_or_create_master_key(self) -> bytes:
        env_key = _fernet_key_from_env()
        if env_key is not None:
            return env_key

        self._base_dir.mkdir(parents=True, exist_ok=True)
        existing = self._read_master_key()
        if existing is not None:
            return existing
        generated = Fernet.generate_key()
        self._persist_new_master_key(generated)
        return generated

    def _persist_new_master_key(self, key: bytes) -> None:
        if self._explicit_base:
            try:
                self._key_path.write_bytes(key)
            except OSError as exc:
                raise CredentialStoreError(
                    "Failed to persist encryption key file.") from exc
            return
        if _save_keyring_password(key.decode("ascii")):
            return
        try:
            self._key_path.write_bytes(key)
        except OSError as exc:
            raise CredentialStoreError(
                "Failed to persist encryption key (keyring and file both failed).",
            ) from exc

    def _read_master_key(self) -> bytes | None:
        env_key = _fernet_key_from_env()
        if env_key is not None:
            return env_key

        if self._explicit_base:
            return self._read_master_key_file_only()

        kr = _get_keyring_password()
        if kr is not None:
            return kr.encode("ascii")

        if self._key_path.exists():
            file_key = self._read_master_key_file_only()
            if file_key is not None and _save_keyring_password(file_key.decode("ascii")):
                try:
                    self._key_path.unlink()
                except OSError:
                    pass
            return file_key

        return None

    def _read_master_key_file_only(self) -> bytes | None:
        if not self._key_path.exists():
            return None
        try:
            key = self._key_path.read_bytes().strip()
        except OSError as exc:
            raise CredentialStoreError(
                "Failed to read encryption key file.") from exc
        if not key:
            raise CredentialStoreError("Encryption key file is empty.")
        return key

    def _read_store_file(self) -> dict[str, str]:
        if not self._store_path.exists():
            return {}
        try:
            raw = self._store_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except OSError as exc:
            raise CredentialStoreError(
                "Failed to read encrypted credential store.") from exc
        except json.JSONDecodeError as exc:
            raise CredentialStoreError(
                "Encrypted credential store is malformed JSON.") from exc
        if not isinstance(payload, dict):
            raise CredentialStoreError(
                "Encrypted credential store must contain an object.")
        out: dict[str, str] = {}
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, str):
                out[key] = value
        return out

    def _write_store_file(self, payload: dict[str, str]) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._store_path.write_text(json.dumps(
                payload, indent=2), encoding="utf-8")
        except OSError as exc:
            raise CredentialStoreError(
                "Failed to write encrypted credential store.") from exc


def _get_keyring_password() -> str | None:
    try:
        import keyring  # noqa: PLC0415
    except ImportError:
        return None
    try:
        return keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    except Exception:
        return None


def _save_keyring_password(password: str) -> bool:
    try:
        import keyring  # noqa: PLC0415
    except ImportError:
        return False
    try:
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, password)
        return True
    except Exception:
        return False
