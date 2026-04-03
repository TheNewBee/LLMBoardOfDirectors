from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from boardroom.models import MeetingState, Message, TerminationReason


def word_jaccard_similarity(a: str, b: str) -> float:
    def tokens(s: str) -> set[str]:
        return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}

    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _last_three(messages: Sequence[Message]) -> tuple[Message, Message, Message] | None:
    if len(messages) < 3:
        return None
    return messages[-3], messages[-2], messages[-1]


def _deadlock_from_similarity(
    m0: Message,
    m1: Message,
    m2: Message,
    threshold: float,
    sim: Callable[[str, str], float],
) -> bool:
    pairs = (
        sim(m0.content, m1.content),
        sim(m1.content, m2.content),
        sim(m0.content, m2.content),
    )
    return min(pairs) >= threshold


def _default_consensus_judge(messages: Sequence[Message]) -> bool:
    agreement_markers = (
        "i agree",
        "we agree",
        "aligned",
        "consensus",
        "proceed",
        "ship it",
        "settled",
    )
    dissent_markers = (
        "i disagree",
        "not aligned",
        "blocker",
        "unresolved",
        "still concerned",
        "however",
    )
    normalized = [message.content.lower() for message in messages]
    if any(marker in text for text in normalized for marker in dissent_markers):
        return False
    agreement_hits = sum(
        1 for text in normalized if any(marker in text for marker in agreement_markers)
    )
    return agreement_hits >= 2


@dataclass(frozen=True)
class TerminationOutcome:
    terminate: bool
    reason: TerminationReason | None = None


@dataclass(frozen=True)
class TerminationDetectorConfig:
    min_turns: int = 5
    max_turns: int = 20
    deadlock_jaccard_threshold: float = 0.85


class TerminationDetector:
    def __init__(
        self,
        config: TerminationDetectorConfig | None = None,
        consensus_judge: Callable[[Sequence[Message]], bool] | None = None,
    ) -> None:
        self._c = config or TerminationDetectorConfig()
        self._consensus_judge = consensus_judge or _default_consensus_judge

    @property
    def max_turns(self) -> int:
        return self._c.max_turns

    def evaluate(
        self,
        state: MeetingState,
        *,
        consensus_judge: Callable[[Sequence[Message]], bool] | None = None,
        pairwise_similarity: Callable[[str, str], float] | None = None,
    ) -> TerminationOutcome:
        c = self._c
        effective_turn_count = max(state.turn_count, len(state.messages))
        if effective_turn_count >= c.max_turns:
            return TerminationOutcome(terminate=True, reason=TerminationReason.MAX_TURNS)

        sim = pairwise_similarity or word_jaccard_similarity
        triple = _last_three(state.messages)
        if (
            triple is not None
            and effective_turn_count >= c.min_turns
            and _deadlock_from_similarity(
                triple[0],
                triple[1],
                triple[2],
                c.deadlock_jaccard_threshold,
                sim,
            )
        ):
            return TerminationOutcome(terminate=True, reason=TerminationReason.DEADLOCK)

        judge = consensus_judge or self._consensus_judge
        if (
            triple is not None
            and effective_turn_count >= c.min_turns
            and judge(state.messages[-3:])
        ):
            return TerminationOutcome(terminate=True, reason=TerminationReason.CONSENSUS)

        return TerminationOutcome(terminate=False, reason=None)
