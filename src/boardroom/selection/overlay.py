from __future__ import annotations

from typing import Any

from boardroom.models import AgentConfig, MeetingState, ModelConfig


def apply_meeting_overlays_to_config(agent_cfg: AgentConfig, meeting: MeetingState) -> AgentConfig:
    model_override: ModelConfig | None = None
    if meeting.llm is not None and agent_cfg.id in meeting.llm.models_by_agent:
        model_override = ModelConfig(
            provider=meeting.llm.provider,
            model=meeting.llm.models_by_agent[agent_cfg.id],
        )
    bias = meeting.bias_intensity_by_agent.get(agent_cfg.id)
    if model_override is None and bias is None:
        return agent_cfg
    updates: dict[str, Any] = {}
    if model_override is not None:
        updates["model_config_override"] = model_override
    if bias is not None:
        updates["bias_intensity"] = bias
    return agent_cfg.model_copy(update=updates)
