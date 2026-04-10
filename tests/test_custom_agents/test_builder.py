from __future__ import annotations

from pathlib import Path

import pytest

from boardroom.custom_agents.builder import CustomAgentBuilder, CustomAgentError
from boardroom.custom_agents.storage import CustomAgentStorage
from boardroom.models import AgentConfig, AgentRole, BiasType


def _sample_config(agent_id: str = "my_analyst") -> AgentConfig:
    return AgentConfig(
        id=agent_id,
        name="Test Analyst",
        role=AgentRole.CUSTOM,
        expertise_domain="financial analysis",
        personality_traits=["analytical"],
        biases=[BiasType.RISK_AVERSION],
        bias_intensity=0.6,
    )


def _builder(tmp_path: Path) -> CustomAgentBuilder:
    storage = CustomAgentStorage(storage_dir=tmp_path)
    return CustomAgentBuilder(storage=storage)


def test_create_agent_succeeds(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    cfg = builder.create(_sample_config())
    assert cfg.id == "my_analyst"
    assert cfg.role == AgentRole.CUSTOM


def test_create_rejects_builtin_id_collision(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    cfg = _sample_config("adversary")
    with pytest.raises(CustomAgentError, match="built-in"):
        builder.create(cfg)


def test_create_rejects_duplicate_id(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    builder.create(_sample_config("unique"))
    with pytest.raises(CustomAgentError, match="already exists"):
        builder.create(_sample_config("unique"))


def test_create_enforces_custom_role(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    cfg = AgentConfig(
        id="bad_role",
        name="Bad",
        role=AgentRole.ADVERSARY,
        expertise_domain="testing",
        personality_traits=["bold"],
    )
    with pytest.raises(CustomAgentError, match="role.*CUSTOM"):
        builder.create(cfg)


def test_update_existing_agent(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    builder.create(_sample_config())
    updated = _sample_config()
    updated = updated.model_copy(update={"name": "Updated Name"})
    result = builder.update(updated)
    assert result.name == "Updated Name"


def test_update_nonexistent_raises(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    with pytest.raises(CustomAgentError, match="does not exist"):
        builder.update(_sample_config("ghost"))


def test_update_enforces_custom_role(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    builder.create(_sample_config("role_check"))
    bad = _sample_config("role_check").model_copy(update={"role": AgentRole.CFO})
    with pytest.raises(CustomAgentError, match="role.*CUSTOM"):
        builder.update(bad)


def test_delete_existing_agent(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    builder.create(_sample_config())
    builder.delete("my_analyst")
    assert not builder.exists("my_analyst")


def test_list_agents(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    builder.create(_sample_config("a"))
    builder.create(_sample_config("b"))
    ids = builder.list_ids()
    assert sorted(ids) == ["a", "b"]


def test_get_agent(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    builder.create(_sample_config())
    cfg = builder.get("my_analyst")
    assert cfg.name == "Test Analyst"
