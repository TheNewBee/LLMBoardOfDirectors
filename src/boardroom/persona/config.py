from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from boardroom.models import AgentConfig, AgentRole, BiasType


@dataclass(frozen=True)
class PersonaConfig:
    name: str
    role: AgentRole
    expertise: str
    biases: list[BiasType]
    communication_style: str
    bias_intensity: float = 0.7

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("PersonaConfig.name must be non-empty.")
        if not self.expertise.strip():
            raise ValueError("PersonaConfig.expertise must be non-empty.")
        if not self.communication_style.strip():
            raise ValueError("PersonaConfig.communication_style must be non-empty.")
        if not 0.0 <= self.bias_intensity <= 1.0:
            raise ValueError("PersonaConfig.bias_intensity must be between 0.0 and 1.0.")


def agent_config_to_persona(agent: AgentConfig) -> PersonaConfig:
    return PersonaConfig(
        name=agent.name,
        role=agent.role,
        expertise=agent.expertise_domain,
        biases=list(agent.biases),
        communication_style="; ".join(agent.personality_traits),
        bias_intensity=agent.bias_intensity,
    )


def persona_to_json(persona: PersonaConfig) -> str:
    payload = {
        "name": persona.name,
        "role": persona.role.value,
        "expertise": persona.expertise,
        "biases": [b.value for b in persona.biases],
        "communication_style": persona.communication_style,
        "bias_intensity": persona.bias_intensity,
    }
    return json.dumps(payload, sort_keys=True)


def persona_from_json(data: str) -> PersonaConfig:
    raw = json.loads(data)
    if not isinstance(raw, dict):
        raise ValueError("Persona JSON must decode to an object.")
    required_fields = {
        "name",
        "role",
        "expertise",
        "biases",
        "communication_style",
        "bias_intensity",
    }
    missing_fields = required_fields.difference(raw)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Persona JSON is missing required fields: {missing}")
    return PersonaConfig(
        name=_require_str(raw, "name"),
        role=AgentRole(_require_str(raw, "role")),
        expertise=_require_str(raw, "expertise"),
        biases=[BiasType(bias) for bias in _require_str_list(raw, "biases")],
        communication_style=_require_str(raw, "communication_style"),
        bias_intensity=float(raw["bias_intensity"]),
    )


def _require_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Persona field '{key}' must be a string.")
    return value


def _require_str_list(raw: dict[str, Any], key: str) -> list[str]:
    value = raw.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Persona field '{key}' must be a list of strings.")
    return value
