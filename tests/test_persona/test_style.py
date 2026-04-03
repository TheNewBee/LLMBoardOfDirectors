from __future__ import annotations

from boardroom.persona.style import StyleEnforcer


def test_style_enforcer_scrubs_as_an_ai_phrase() -> None:
    se = StyleEnforcer()
    raw = "As an AI language model, I cannot endorse that plan."
    cleaned = se.scrub_leaks(raw)
    assert "as an ai" not in cleaned.lower()
    assert "language model" not in cleaned.lower()


def test_style_enforcer_scrubs_helpful_assistant_phrase() -> None:
    se = StyleEnforcer()
    raw = "I am here to help you with your request today."
    cleaned = se.scrub_leaks(raw)
    assert "here to help" not in cleaned.lower()


def test_style_instructions_include_perspective_rules() -> None:
    se = StyleEnforcer()
    block = se.style_prompt_block()
    lower = block.lower()
    assert "first person" in lower or "first-person" in lower
    assert "you" in lower or "second" in lower


def test_professional_tone_flags_casual_markers() -> None:
    se = StyleEnforcer()
    issues = se.professional_tone_issues("lol this is kinda broken!!!")
    assert issues


def test_perspective_issues_require_first_and_second_person() -> None:
    se = StyleEnforcer()
    issues = se.perspective_issues("The company should cut scope next quarter.")
    assert issues
