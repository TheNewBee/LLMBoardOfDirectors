from __future__ import annotations

from pathlib import Path

import pytest

from boardroom.secrets import CredentialStore, CredentialStoreError


def test_store_set_and_get_round_trip(tmp_path: Path) -> None:
    store = CredentialStore(base_dir=tmp_path)
    store.set("openrouter", "sk-test-123")
    assert store.has("openrouter") is True
    assert store.get("openrouter") == "sk-test-123"


def test_store_get_returns_none_when_provider_missing(tmp_path: Path) -> None:
    store = CredentialStore(base_dir=tmp_path)
    assert store.get("openrouter") is None


def test_store_set_overwrites_existing_value(tmp_path: Path) -> None:
    store = CredentialStore(base_dir=tmp_path)
    store.set("openrouter", "sk-old")
    store.set("openrouter", "sk-new")
    assert store.get("openrouter") == "sk-new"


def test_store_raises_for_corrupted_ciphertext(tmp_path: Path) -> None:
    store = CredentialStore(base_dir=tmp_path)
    store.set("openrouter", "sk-real")
    store_file = tmp_path / "credentials.json"
    store_file.write_text(
        '{"openrouter":"not-a-valid-token"}', encoding="utf-8")
    with pytest.raises(CredentialStoreError):
        store.get("openrouter")
