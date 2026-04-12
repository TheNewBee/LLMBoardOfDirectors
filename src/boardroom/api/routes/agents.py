from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from boardroom.api.schemas import AgentSummaryResponse, AgentsResponse
from boardroom.custom_agents.builder import CustomAgentBuilder, CustomAgentError
from boardroom.custom_agents.storage import CustomAgentStorage
from boardroom.models import AgentConfig
from boardroom.registry import AgentRegistry

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _custom_builder() -> CustomAgentBuilder:
    storage = CustomAgentStorage(storage_dir=Path(".boardroom/custom_agents"))
    return CustomAgentBuilder(storage=storage)


@router.get("", response_model=AgentsResponse)
def list_agents() -> AgentsResponse:
    reg = AgentRegistry()
    rows: list[AgentSummaryResponse] = []
    for agent_id in reg.list_agent_ids():
        cfg = reg.get_config(agent_id)
        rows.append(
            AgentSummaryResponse(
                id=cfg.id,
                name=cfg.name,
                role=cfg.role.value,
                expertise_domain=cfg.expertise_domain,
                personality_traits=cfg.personality_traits,
                biases=[bias.value for bias in cfg.biases],
                bias_intensity=cfg.bias_intensity,
            )
        )
    return AgentsResponse(agents=rows)


@router.post("/custom", response_model=AgentSummaryResponse)
def create_custom_agent(config: AgentConfig) -> AgentSummaryResponse:
    builder = _custom_builder()
    try:
        created = builder.create(config)
    except CustomAgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentSummaryResponse(
        id=created.id,
        name=created.name,
        role=created.role.value,
        expertise_domain=created.expertise_domain,
        personality_traits=created.personality_traits,
        biases=[bias.value for bias in created.biases],
        bias_intensity=created.bias_intensity,
    )


@router.put("/custom/{agent_id}", response_model=AgentSummaryResponse)
def update_custom_agent(agent_id: str, config: AgentConfig) -> AgentSummaryResponse:
    if config.id != agent_id:
        raise HTTPException(status_code=400, detail="Path agent_id must match payload id.")
    builder = _custom_builder()
    try:
        updated = builder.update(config)
    except CustomAgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentSummaryResponse(
        id=updated.id,
        name=updated.name,
        role=updated.role.value,
        expertise_domain=updated.expertise_domain,
        personality_traits=updated.personality_traits,
        biases=[bias.value for bias in updated.biases],
        bias_intensity=updated.bias_intensity,
    )


@router.delete("/custom/{agent_id}")
def delete_custom_agent(agent_id: str) -> dict[str, str]:
    builder = _custom_builder()
    try:
        builder.delete(agent_id)
    except CustomAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}
