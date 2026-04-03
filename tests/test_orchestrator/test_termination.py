from __future__ import annotations

from datetime import datetime

from boardroom.models import Briefing, MeetingState, Message, TerminationReason
from boardroom.orchestrator.termination import (
    TerminationDetector,
    TerminationDetectorConfig,
    TerminationOutcome,
    word_jaccard_similarity,
)


def _msg(agent_id: str, content: str) -> Message:
    return Message(
        agent_id=agent_id,
        agent_name=agent_id,
        content=content,
        timestamp=datetime(2025, 1, 1, 12, 0, 0),
    )


def _state(turn_count: int, messages: list[Message]) -> MeetingState:
    return MeetingState(
        meeting_id="m1",
        briefing=Briefing(text="Topic.", objectives=["o"]),
        selected_agents=["a", "b"],
        messages=messages,
        turn_count=turn_count,
    )


def test_max_turns_terminates_regardless_of_consensus() -> None:
    det = TerminationDetector()
    state = _state(
        20,
        [_msg("a", "x"), _msg("b", "y")],
    )
    out = det.evaluate(state, consensus_judge=lambda _: True)
    assert out == TerminationOutcome(terminate=True, reason=TerminationReason.MAX_TURNS)


def test_consensus_blocked_before_min_turns() -> None:
    det = TerminationDetector()
    last_three = [_msg("a", "we agree"), _msg("b", "aligned"), _msg("a", "ship it")]
    state = _state(4, last_three)
    out = det.evaluate(state, consensus_judge=lambda _: True)
    assert out.terminate is False


def test_consensus_after_min_turns_with_judge() -> None:
    det = TerminationDetector()
    last_three = [
        _msg("a", "I agree we should proceed with the EU rollout timeline."),
        _msg("b", "Finance is aligned; no further blockers from my side."),
        _msg("a", "Then we have consensus to ship before quarter end."),
    ]
    state = _state(5, last_three)
    out = det.evaluate(state, consensus_judge=lambda _: True)
    assert out == TerminationOutcome(terminate=True, reason=TerminationReason.CONSENSUS)


def test_default_consensus_judge_can_terminate_on_clear_alignment() -> None:
    det = TerminationDetector()
    last_three = [
        _msg("a", "I agree we should proceed with the rollout."),
        _msg("b", "I am aligned; finance is comfortable proceeding."),
        _msg("a", "Then we have consensus and can ship it."),
    ]
    state = _state(5, last_three)
    out = det.evaluate(state)
    assert out == TerminationOutcome(terminate=True, reason=TerminationReason.CONSENSUS)


def test_consensus_judge_false_no_terminate() -> None:
    det = TerminationDetector()
    last_three = [_msg("a", "a"), _msg("b", "b"), _msg("a", "c")]
    state = _state(10, last_three)
    out = det.evaluate(state, consensus_judge=lambda _: False)
    assert out.terminate is False


def test_deadlock_three_consecutive_similar_turns_after_min() -> None:
    det = TerminationDetector(TerminationDetectorConfig(deadlock_jaccard_threshold=0.85))
    text = (
        "We must reduce spend the same way as before without new data "
        "and repeat the same argument again."
    )
    last_three = [_msg("a", text), _msg("b", text), _msg("a", text)]
    state = _state(5, last_three)
    out = det.evaluate(state, consensus_judge=lambda _: False)
    assert out == TerminationOutcome(terminate=True, reason=TerminationReason.DEADLOCK)


def test_deadlock_not_triggered_below_min_turns() -> None:
    det = TerminationDetector(TerminationDetectorConfig(deadlock_jaccard_threshold=0.85))
    text = "Same repeated argument without new information."
    last_three = [_msg("a", text), _msg("b", text), _msg("a", text)]
    state = _state(4, last_three)
    out = det.evaluate(state, consensus_judge=lambda _: False)
    assert out.terminate is False


def test_deadlock_uses_injectable_similarity() -> None:
    det = TerminationDetector()

    def always_similar(_a: str, _b: str) -> float:
        return 1.0

    last_three = [_msg("a", "x"), _msg("b", "y"), _msg("a", "z")]
    state = _state(5, last_three)
    out = det.evaluate(
        state,
        consensus_judge=lambda _: False,
        pairwise_similarity=always_similar,
    )
    assert out == TerminationOutcome(terminate=True, reason=TerminationReason.DEADLOCK)


def test_consensus_without_judge_never_fires() -> None:
    det = TerminationDetector()
    state = _state(10, [_msg("a", "1"), _msg("b", "2"), _msg("a", "3")])
    out = det.evaluate(state, consensus_judge=lambda _: False)
    assert out.terminate is False


def test_effective_turn_count_uses_messages_when_turn_count_lags() -> None:
    det = TerminationDetector()
    messages = [
        _msg("a", "I agree we should proceed."),
        _msg("b", "I am aligned and have no blocker."),
        _msg("a", "Then we have consensus."),
        _msg("b", "I agree."),
        _msg("a", "Proceed."),
    ]
    state = _state(4, messages)
    out = det.evaluate(state)
    assert out == TerminationOutcome(terminate=True, reason=TerminationReason.CONSENSUS)


def test_word_jaccard_similarity_symmetric() -> None:
    a = "foo bar baz"
    b = "foo bar qux"
    j1 = word_jaccard_similarity(a, b)
    j2 = word_jaccard_similarity(b, a)
    assert j1 == j2
    assert 0 < j1 < 1
