from __future__ import annotations

import re
from typing import ClassVar


class StyleEnforcer:
    _LEAK_SENTENCE: ClassVar[re.Pattern[str]] = re.compile(r"(?is)\bas an ai\b.*?(?=[.!?]|\Z)")
    _HELP_SENTENCE: ClassVar[re.Pattern[str]] = re.compile(
        r"(?is)\bi am here to help\b.*?(?=[.!?]|\Z)"
    )

    def style_prompt_block(self) -> str:
        return (
            "Voice and perspective: speak in the first person as this board member. "
            'Address other participants as "you" / "your" when engaging them. '
            "Stay in character; do not describe yourself as an AI, chatbot, or assistant. "
            'Do not use phrases such as "As an AI" or "I am here to help." '
            "Keep tone professional, concise, and debate-appropriate."
        )

    def scrub_leaks(self, text: str) -> str:
        t = self._LEAK_SENTENCE.sub("", text)
        t = self._HELP_SENTENCE.sub("", t)
        t = re.sub(r"(?i)\blanguage model\b", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def professional_tone_issues(self, text: str) -> list[str]:
        issues: list[str] = []
        lower = text.lower()
        if "lol" in lower or "lmao" in lower:
            issues.append("avoid internet slang")
        if "kinda" in lower or "sorta" in lower:
            issues.append("avoid vague informal fillers")
        if text.count("!") >= 3:
            issues.append("reduce excessive exclamation marks")
        return issues

    def perspective_issues(self, text: str) -> list[str]:
        lower = f" {text.lower()} "
        issues: list[str] = []
        has_first_person = any(
            token in lower for token in (" i ", " i'm ", " i’ve ", " i’d ", " my ")
        )
        has_second_person = any(
            token in lower for token in (" you ", " your ", " you're ", " you’ve ", " you’d ")
        )
        if not has_first_person:
            issues.append("use first-person perspective")
        if not has_second_person:
            issues.append("address another participant directly when making a point")
        return issues
