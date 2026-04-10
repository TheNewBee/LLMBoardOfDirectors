from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardroom.custom_agents.storage import CustomAgentStorage
from boardroom.models import AgentConfig, AgentRole, BiasType


def _sample_config(agent_id: str = "my_analyst") -> AgentConfig:
    return AgentConfig(
        id=agent_id,
        name="Test Analyst",
        role=AgentRole.CUSTOM,
        expertise_domain="financial analysis and market research",
        personality_traits=["analytical", "detail-oriented"],
        biases=[BiasType.RISK_AVERSION],
        bias_intensity=0.6,
    )


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    cfg = _sample_config()
    storage.save(cfg)

    loaded = storage.load("my_analyst")
    assert loaded.id == cfg.id
    assert loaded.name == cfg.name
    assert loaded.role == AgentRole.CUSTOM
    assert loaded.expertise_domain == cfg.expertise_domain


def test_save_creates_json_file(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    storage.save(_sample_config())

    path = tmp_path / "my_analyst.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["id"] == "my_analyst"


def test_load_nonexistent_raises(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        storage.load("no_such_agent")


def test_list_agents_empty(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    assert storage.list_ids() == []


def test_list_agents_returns_saved(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    storage.save(_sample_config("alpha"))
    storage.save(_sample_config("beta"))

    ids = storage.list_ids()
    assert sorted(ids) == ["alpha", "beta"]


def test_delete_removes_file(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    storage.save(_sample_config())
    storage.delete("my_analyst")
    assert storage.list_ids() == []


def test_delete_nonexistent_raises(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        storage.delete("ghost")


def test_exists(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    assert not storage.exists("my_analyst")
    storage.save(_sample_config())
    assert storage.exists("my_analyst")


def test_load_all(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    storage.save(_sample_config("a"))
    storage.save(_sample_config("b"))

    all_agents = storage.load_all()
    assert len(all_agents) == 2
    ids = {a.id for a in all_agents}
    assert ids == {"a", "b"}


def test_rejects_path_traversal_ids(tmp_path: Path) -> None:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    with pytest.raises(ValueError, match="path traversal"):
        storage.exists("../../escape")
