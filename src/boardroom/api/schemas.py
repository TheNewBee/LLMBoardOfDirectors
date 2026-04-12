from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BriefingPayload(BaseModel):
    text: str = Field(min_length=1)
    objectives: list[str] = Field(default_factory=list)


class MeetingStartPayload(BaseModel):
    meeting_id: str | None = None
    briefing: BriefingPayload
    agents: list[str] = Field(min_length=2, max_length=6)
    models_by_agent: dict[str, str] = Field(default_factory=dict)
    bias_intensity_by_agent: dict[str, float] = Field(default_factory=dict)
    enable_web_search: bool = True
    max_turns: int | None = Field(default=None, ge=1)


class MeetingPreviewResponse(BaseModel):
    meeting_id: str
    agents: list[str]
    can_start: bool


class AgentSummaryResponse(BaseModel):
    id: str
    name: str
    role: str
    expertise_domain: str
    personality_traits: list[str]
    biases: list[str]
    bias_intensity: float


class AgentsResponse(BaseModel):
    agents: list[AgentSummaryResponse]


class ActiveMeetingResponse(BaseModel):
    meeting_id: str
    status: str
    turn_count: int = 0
    current_speaker: str | None = None
    started_at: datetime
    selected_agents: list[str] = Field(default_factory=list)


class MeetingsResponse(BaseModel):
    meetings: list[ActiveMeetingResponse]


class ConfigResponse(BaseModel):
    config: dict[str, Any]
    config_path: str | None
    has_openrouter_api_key: bool


class ConfigPatchRequest(BaseModel):
    patch: dict[str, Any]


class ValidateKeyRequest(BaseModel):
    provider: str = "openrouter"
    model: str | None = None


class ValidateKeyResponse(BaseModel):
    ok: bool
    provider: str
    model: str


class StoreKeyRequest(BaseModel):
    provider: str = "openrouter"
    api_key: str = Field(min_length=1)
    validate_after_store: bool = True
    model: str | None = None


class StoreKeyResponse(BaseModel):
    ok: bool
    provider: str
    validated: bool
    model: str | None = None


class ProviderModel(BaseModel):
    id: str
    name: str


class ProviderModelsResponse(BaseModel):
    provider: str
    models: list[ProviderModel]
    cached: bool
