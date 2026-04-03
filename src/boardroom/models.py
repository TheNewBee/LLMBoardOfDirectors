from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentRole(str, Enum):
    ADVERSARY = "adversary"
    DATA_SPECIALIST = "data_specialist"
    STRATEGIST = "strategist"
    CFO = "cfo"
    TECH_DIRECTOR = "tech_director"
    CUSTOM = "custom"


class BiasType(str, Enum):
    RISK_AVERSION = "risk_aversion"
    OVER_ENGINEERING = "over_engineering"
    OPTIMISM_BIAS = "optimism_bias"
    PESSIMISM_BIAS = "pessimism_bias"
    COST_FOCUS = "cost_focus"
    SPEED_FOCUS = "speed_focus"


class TerminationReason(str, Enum):
    CONSENSUS = "consensus"
    DEADLOCK = "deadlock"
    MAX_TURNS = "max_turns"
    CHAIRMAN_INTERRUPT = "chairman_interrupt"


class Skill(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    callable_id: str = Field(min_length=1)
    parameters_schema: dict[str, Any] = Field(default_factory=dict)


class ProviderConfig(BaseModel):
    api_key_env: str = Field(min_length=1)
    base_url: str = Field(min_length=1)

    @field_validator("api_key_env")
    @classmethod
    def validate_api_key_env(cls, value: str) -> str:
        if value.upper() != value:
            raise ValueError("api_key_env must be uppercase")
        return value


class ModelConfig(BaseModel):
    provider: str = Field(default="openrouter", min_length=1)
    model: str = Field(default="anthropic/claude-sonnet-4", min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, gt=0)


class AgentConfig(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: AgentRole
    expertise_domain: str = Field(min_length=1)
    personality_traits: list[str] = Field(default_factory=list)
    biases: list[BiasType] = Field(default_factory=list)
    bias_intensity: float = Field(default=0.7, ge=0.0, le=1.0)
    skills: list[Skill] = Field(default_factory=list)
    knowledge_source_preferences: dict[str,
                                       float] = Field(default_factory=dict)
    staleness_threshold_days: int = Field(default=7, gt=0)
    model_config_override: ModelConfig | None = None

    @field_validator("personality_traits")
    @classmethod
    def strip_personality_traits(cls, traits: list[str]) -> list[str]:
        cleaned = [trait.strip() for trait in traits if trait.strip()]
        if not cleaned:
            raise ValueError(
                "personality_traits must include at least one trait")
        return cleaned

    @field_validator("knowledge_source_preferences")
    @classmethod
    def validate_source_preferences(cls, value: dict[str, float]) -> dict[str, float]:
        for weight in value.values():
            if weight < 0:
                raise ValueError(
                    "knowledge source preference weights must be non-negative")
        return value


class Message(BaseModel):
    agent_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    content: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)


class Briefing(BaseModel):
    text: str = Field(min_length=1)
    objectives: list[str] = Field(default_factory=list)
    alpha_files: list[Path] = Field(default_factory=list)
    alpha_content: dict[str, str] = Field(default_factory=dict)

    @field_validator("objectives")
    @classmethod
    def validate_objectives(cls, objectives: list[str]) -> list[str]:
        cleaned = [objective.strip()
                   for objective in objectives if objective.strip()]
        if not cleaned:
            raise ValueError("objectives must include at least one item")
        return cleaned

    @model_validator(mode="after")
    def validate_alpha_content(self) -> "Briefing":
        if self.alpha_content and not self.alpha_files:
            raise ValueError(
                "alpha_files must be provided when alpha_content is present")
        return self


class Transcript(BaseModel):
    meeting_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    path: Path
    kill_sheet_path: Path | None = None
    consensus_roadmap_path: Path | None = None
    message_count: int = Field(default=0, ge=0)


class MeetingLLMSelection(BaseModel):
    """Runtime LLM choices persisted with the meeting (Phase 1: OpenRouter)."""

    provider: str = Field(default="openrouter", min_length=1)
    models_by_agent: dict[str, str] = Field(default_factory=dict)


class MeetingState(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    meeting_id: str = Field(min_length=1)
    briefing: Briefing
    selected_agents: list[str] = Field(default_factory=list, max_length=6)
    messages: list[Message] = Field(default_factory=list)
    turn_count: int = Field(default=0, ge=0)
    current_speaker: str | None = None
    debate_topics: list[str] = Field(default_factory=list)
    unresolved_points: list[str] = Field(default_factory=list)
    start_time: datetime = Field(default_factory=datetime.utcnow)
    termination_reason: TerminationReason | None = None
    persisted_transcript: Transcript | None = None
    llm: MeetingLLMSelection | None = None
    bias_intensity_by_agent: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_selected_agents_for_phase(self) -> "MeetingState":
        n = len(self.selected_agents)
        if n == 1:
            raise ValueError(
                "selected_agents must be empty (pending agent selection) or include 2-6 agents"
            )
        return self

    def with_current_speaker(self, speaker_id: str | None) -> MeetingState:
        return self.model_copy(update={"current_speaker": speaker_id})

    def with_appended_message(
        self, message: Message, *, bump_turn_count: bool = True
    ) -> MeetingState:
        next_turn = self.turn_count + 1 if bump_turn_count else self.turn_count
        return self.model_copy(
            update={
                "messages": [*self.messages, message],
                "turn_count": next_turn,
                "current_speaker": message.agent_id,
            },
        )

    def with_termination(self, reason: TerminationReason) -> MeetingState:
        return self.model_copy(update={"termination_reason": reason})


class PathsConfig(BaseModel):
    outputs_dir: Path = Path("transcripts")


class AppConfig(BaseModel):
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    default_model: ModelConfig = Field(default_factory=ModelConfig)
    agent_models: dict[str, ModelConfig] = Field(default_factory=dict)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    rate_limit_interval_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum seconds between consecutive LLM generation requests.",
    )

    @field_validator("providers")
    @classmethod
    def validate_providers(cls, providers: dict[str, ProviderConfig]) -> dict[str, ProviderConfig]:
        if "openrouter" not in providers:
            raise ValueError("providers must include an openrouter entry")
        return providers

    def model_for_agent(self, agent_id: str, role: AgentRole | None = None) -> ModelConfig:
        if agent_id in self.agent_models:
            return self.agent_models[agent_id]
        if role is not None and role.value in self.agent_models:
            return self.agent_models[role.value]
        return self.default_model
