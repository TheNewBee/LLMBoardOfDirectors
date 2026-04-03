from __future__ import annotations

from boardroom.models import Briefing
from boardroom.persona.bias import BiasApplicator
from boardroom.persona.config import PersonaConfig
from boardroom.persona.style import StyleEnforcer
from boardroom.persona.templates import role_template


class PersonaConsistencyError(ValueError):
    pass


class PersonaEngine:
    def __init__(
        self,
        style: StyleEnforcer | None = None,
        bias: BiasApplicator | None = None,
    ) -> None:
        self._style = style or StyleEnforcer()
        self._bias = bias or BiasApplicator()

    def apply_persona(self, persona: PersonaConfig, briefing: Briefing | None = None) -> str:
        intro = role_template(persona.role).format(
            name=persona.name,
            expertise=persona.expertise,
        )
        style = self._style.style_prompt_block()
        bias = self._bias.bias_prompt_fragment(persona)
        comm = f"Communication style: {persona.communication_style}."
        blocks = [intro, comm, style, bias]
        if briefing is not None:
            objectives = "; ".join(briefing.objectives)
            alpha_note = ""
            if briefing.alpha_content:
                alpha_note = (
                    f" Supporting materials are attached ({len(briefing.alpha_content)} file(s)); "
                    "reference them when relevant."
                )
            blocks.append(
                f"Chair briefing (context): {briefing.text.strip()}\n"
                f"Meeting objectives: {objectives}.{alpha_note}"
            )
        return "\n\n".join(blocks)

    def validate_consistency(
        self,
        persona: PersonaConfig,
        prior_turn_contents: list[str],
        candidate_turn: str,
    ) -> None:
        cleaned_candidate = self._style.scrub_leaks(candidate_turn)
        if not cleaned_candidate.strip():
            raise PersonaConsistencyError(
                f"{persona.name} produced an empty turn after style normalization."
            )

        if prior_turn_contents:
            previous_turns = {
                self._style.scrub_leaks(turn).strip().lower()
                for turn in prior_turn_contents
                if turn.strip()
            }
            if cleaned_candidate.strip().lower() in previous_turns:
                raise PersonaConsistencyError(
                    f"{persona.name} is repeating an earlier contribution; advance the argument.",
                )

        lower = candidate_turn.lower()
        if "as an ai" in lower or "i am here to help" in lower:
            raise PersonaConsistencyError("Turn contains disallowed assistant-disclosure phrasing.")
        issues = self._style.professional_tone_issues(cleaned_candidate)
        issues.extend(self._style.perspective_issues(cleaned_candidate))
        if issues:
            raise PersonaConsistencyError(
                f"{persona.name} broke persona communication rules: {', '.join(issues)}"
            )
