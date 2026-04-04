"""Encrypted credential storage for provider API keys."""

from boardroom.secrets.store import CredentialStore, CredentialStoreError

__all__ = ["CredentialStore", "CredentialStoreError"]
