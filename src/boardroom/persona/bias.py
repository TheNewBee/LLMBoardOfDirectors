from __future__ import annotations

from boardroom.models import BiasType
from boardroom.persona.config import PersonaConfig


_BIAS_LINES: dict[BiasType, str] = {
    BiasType.RISK_AVERSION: (
        "Lean away from avoidable risk; stress downside scenarios, "
        "guards, and what must be true for the plan to be safe. "
        "Bias intensity: {intensity:.2f} (0=neutral, 1=strong)."
    ),
    BiasType.OVER_ENGINEERING: (
        "Favor robust, durable systems over minimal shortcuts; question whether "
        "the design will survive scale and operational reality. "
        "Bias intensity: {intensity:.2f}."
    ),
    BiasType.OPTIMISM_BIAS: (
        "Highlight upside, momentum, and paths to success while still naming key risks. "
        "Bias intensity: {intensity:.2f}."
    ),
    BiasType.PESSIMISM_BIAS: (
        "Stress what could go wrong and where optimism may be unwarranted. "
        "Bias intensity: {intensity:.2f}."
    ),
    BiasType.COST_FOCUS: (
        "Prioritize unit economics, burn, and capital efficiency. "
        "Bias intensity: {intensity:.2f}."
    ),
    BiasType.SPEED_FOCUS: (
        "Prioritize time-to-learning and shipping; challenge slow or heavy processes. "
        "Bias intensity: {intensity:.2f}."
    ),
}


class BiasApplicator:
    def bias_prompt_fragment(self, persona: PersonaConfig) -> str:
        if not persona.biases:
            return (
                "Cognitive biases: none specified; stay balanced unless the role demands otherwise."
            )
        parts: list[str] = []
        for bias in persona.biases:
            template = _BIAS_LINES.get(bias)
            if template is None:
                continue
            parts.append(template.format(intensity=persona.bias_intensity))
        if not parts:
            return "Cognitive biases: (configured biases have no prompt mapping)."
        return (
            "Apply the following leanings to how you argue (not as confessions, but as reasoning lenses):\n- "
            + "\n- ".join(parts)
        )
