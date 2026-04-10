from __future__ import annotations

import logging

from boardroom.knowledge.store import KnowledgeVectorStore
from boardroom.memory.agent_memory import AgentMemoryStore

_LOG = logging.getLogger(__name__)


def _format_with_budget(
    *,
    header: str,
    lines: list[str],
    max_tokens: int,
) -> str:
    if not lines:
        return ""
    char_budget = max_tokens * 4
    selected: list[str] = [header]
    chars_used = len(header) + 1
    for line in lines:
        line_with_newline = len(line) + 1
        if chars_used + line_with_newline > char_budget:
            break
        selected.append(line)
        chars_used += line_with_newline
    if len(selected) == 1:
        return ""
    return "\n".join(selected)


def build_agent_context_parts(
    *,
    agent_id: str,
    briefing_text: str,
    knowledge_store: KnowledgeVectorStore | None = None,
    memory_store: AgentMemoryStore | None = None,
    max_knowledge_tokens: int = 5000,
    max_memory_tokens: int = 2000,
) -> tuple[str, str]:
    """Return separate knowledge and memory prompt sections."""
    knowledge_context = ""
    memory_context = ""

    if knowledge_store:
        try:
            items = knowledge_store.retrieve(
                agent_id,
                query=briefing_text,
                limit=20,
            )
            kb_lines = [f"- [{item.title}]({item.url}): {item.content[:300]}" for item in items]
            knowledge_context = _format_with_budget(
                header="## Domain Knowledge",
                lines=kb_lines,
                max_tokens=max_knowledge_tokens,
            )
        except (OSError, RuntimeError, ValueError):
            _LOG.warning("Failed to retrieve knowledge for agent=%s", agent_id, exc_info=True)

    if memory_store:
        try:
            memories = memory_store.retrieve(
                agent_id,
                query=briefing_text,
                limit=10,
            )
            mem_lines = [f"- ({mem.memory_type}) {mem.content[:200]}" for mem in memories]
            memory_context = _format_with_budget(
                header="## Past Meeting Memory",
                lines=mem_lines,
                max_tokens=max_memory_tokens,
            )
        except (OSError, RuntimeError, ValueError):
            _LOG.warning("Failed to retrieve memory for agent=%s", agent_id, exc_info=True)

    return knowledge_context, memory_context


def build_agent_context(
    *,
    agent_id: str,
    briefing_text: str,
    knowledge_store: KnowledgeVectorStore | None = None,
    memory_store: AgentMemoryStore | None = None,
    max_knowledge_tokens: int = 5000,
    max_memory_tokens: int = 2000,
) -> str:
    """Assemble agent context from knowledge base and memory for prompt injection."""
    knowledge_context, memory_context = build_agent_context_parts(
        agent_id=agent_id,
        briefing_text=briefing_text,
        knowledge_store=knowledge_store,
        memory_store=memory_store,
        max_knowledge_tokens=max_knowledge_tokens,
        max_memory_tokens=max_memory_tokens,
    )
    sections = [s for s in (knowledge_context, memory_context) if s]
    return "\n\n".join(sections)
