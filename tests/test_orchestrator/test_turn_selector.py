from __future__ import annotations

from boardroom.models import AgentConfig, AgentRole, Briefing, MeetingState, Message
from boardroom.orchestrator.turn_selector import TurnSelector, TurnSelectorConfig


def _agent(
    aid: str,
    role: AgentRole,
    expertise: str,
) -> AgentConfig:
    return AgentConfig(
        id=aid,
        name=aid.upper(),
        role=role,
        expertise_domain=expertise,
        personality_traits=["test"],
    )


def _state(
    briefing_text: str,
    messages: list[Message],
    selected: list[str] | None = None,
) -> MeetingState:
    briefing = Briefing(
        text=briefing_text,
        objectives=["obj"],
    )
    ids = selected or ["adv", "exp_a", "exp_b"]
    return MeetingState(
        meeting_id="m1",
        briefing=briefing,
        selected_agents=ids,
        messages=messages,
        turn_count=len(messages),
    )


def test_weight_favors_expertise_match_to_current_context() -> None:
    agents = {
        "adv": _agent("adv", AgentRole.ADVERSARY, "debate and critique"),
        "exp_a": _agent("exp_a", AgentRole.CFO, "unit economics and treasury"),
        "exp_b": _agent("exp_b", AgentRole.TECH_DIRECTOR, "kubernetes and platform"),
    }
    state = _state(
        "We should cut cloud spend and fix unit economics next quarter.",
        messages=[],
    )
    sel = TurnSelector(TurnSelectorConfig(adversary_boost=0.0, adversary_silence_turns=99))
    nxt = sel.next_speaker(state, agents)
    assert nxt == "exp_a"


def test_no_forced_adversary_opening_without_prior_silence() -> None:
    agents = {
        "adv": _agent("adv", AgentRole.ADVERSARY, "debate and critique"),
        "exp_a": _agent("exp_a", AgentRole.CFO, "unit economics and treasury"),
    }
    state = _state(
        "We should cut cloud spend and fix unit economics next quarter.",
        messages=[],
        selected=["adv", "exp_a"],
    )
    sel = TurnSelector()
    assert sel.next_speaker(state, agents) == "exp_a"


def test_participation_balancing_prefers_underrepresented_agent() -> None:
    agents = {
        "a": _agent("a", AgentRole.CFO, "finance and treasury"),
        "b": _agent("b", AgentRole.CFO, "finance and treasury"),
    }
    msgs = [
        Message(agent_id="a", agent_name="A", content="First on finance."),
        Message(agent_id="a", agent_name="A", content="Second on finance."),
    ]
    state = _state("Finance review.", msgs, selected=["a", "b"])
    sel = TurnSelector(
        TurnSelectorConfig(
            adversary_boost=0.0,
            adversary_silence_turns=99,
            participation_weight=5.0,
            expertise_weight=0.1,
        )
    )
    nxt = sel.next_speaker(state, agents)
    assert nxt == "b"


def test_adversary_injection_after_silence() -> None:
    agents = {
        "adv": _agent("adv", AgentRole.ADVERSARY, "debate only"),
        "cfo": _agent("cfo", AgentRole.CFO, "finance"),
    }
    msgs = [
        Message(agent_id="cfo", agent_name="C", content="One."),
        Message(agent_id="cfo", agent_name="C", content="Two."),
        Message(agent_id="cfo", agent_name="C", content="Three."),
    ]
    state = _state("Finance topic.", msgs, selected=["adv", "cfo"])
    sel = TurnSelector(
        TurnSelectorConfig(
            adversary_silence_turns=3,
            adversary_boost=100.0,
            participation_weight=0.01,
            expertise_weight=0.01,
        )
    )
    nxt = sel.next_speaker(state, agents)
    assert nxt == "adv"


def test_deterministic_tie_breaker_uses_agent_id() -> None:
    agents = {
        "z": _agent("z", AgentRole.STRATEGIST, "strategy"),
        "m": _agent("m", AgentRole.STRATEGIST, "strategy"),
    }
    state = _state("Strategy alignment.", [], selected=["z", "m"])
    sel = TurnSelector(TurnSelectorConfig(adversary_boost=0.0, adversary_silence_turns=99))
    assert sel.next_speaker(state, agents) == "m"
