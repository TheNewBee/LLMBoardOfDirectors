from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    summary: str
    example_args: dict[str, Any]


PYTHON_EXEC_TOOL = ToolSpec(
    name="python_exec",
    summary="Run a short Python snippet for quick calculations.",
    example_args={"code": "print(2+2)"},
)

WEB_SEARCH_TOOL = ToolSpec(
    name="web_search",
    summary="Run a short web search for timely facts.",
    example_args={"query": "latest market data", "max_results": 3},
)

TOOL_SPECS: tuple[ToolSpec, ...] = (
    PYTHON_EXEC_TOOL,
    WEB_SEARCH_TOOL,
)


def known_tool_names() -> set[str]:
    return {spec.name for spec in TOOL_SPECS}


def tool_prompt_guidance() -> str:
    specs = list(TOOL_SPECS)
    examples = []
    for spec in specs:
        payload = {"name": spec.name, "args": spec.example_args}
        payload_json = json.dumps(payload, ensure_ascii=True)
        payload_for_prompt = payload_json.replace("{", "{{").replace("}", "}}")
        examples.append(
            "```tool\n"
            f"{payload_for_prompt}\n"
            "```"
        )
    joined = "\nor\n".join(examples)
    names = ", ".join(f"`{spec.name}`" for spec in specs)
    return (
        "You may use tools when they genuinely help your reasoning in this discussion "
        "(e.g. quick calculations, sanity checks, or brief web lookups for timely facts). "
        "When you use a tool, emit one fenced JSON tool block using this exact shape:\n"
        f"{joined}\n"
        f"Use only {names}. Keep normal analysis outside the tool block."
    )
