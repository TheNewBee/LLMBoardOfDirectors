from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from boardroom.models import Briefing

SUPPORTED_ALPHA_SUFFIXES: frozenset[str] = frozenset(
    {".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv"}
)


def _normalize_path(p: str | Path) -> Path:
    return Path(p).expanduser()


def load_alpha_files(paths: Sequence[str | Path]) -> tuple[list[Path], dict[str, str]]:
    """Read supported text-like Alpha files as UTF-8. Keys are resolved path strings."""
    if not paths:
        return [], {}

    seen: set[str] = set()
    alpha_files: list[Path] = []
    alpha_content: dict[str, str] = {}

    for raw in paths:
        path = _normalize_path(raw).resolve()
        key = path.as_posix()
        if key in seen:
            continue
        seen.add(key)

        if not path.is_file():
            raise FileNotFoundError(f"Alpha file not found or not a file: {path}")

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_ALPHA_SUFFIXES:
            raise ValueError(
                f"Unsupported Alpha file type {suffix!r} for {path}; "
                f"supported: {', '.join(sorted(SUPPORTED_ALPHA_SUFFIXES))}"
            )

        text = path.read_text(encoding="utf-8")
        alpha_files.append(path)
        alpha_content[key] = text

    return alpha_files, alpha_content


def build_briefing(
    idea: str,
    objectives: Sequence[str],
    alpha_paths: Sequence[str | Path] | None = None,
) -> Briefing:
    """Construct a validated Briefing from Chairman inputs and optional Alpha paths."""
    cleaned_idea = idea.strip()
    alpha_paths = alpha_paths or []
    alpha_files, alpha_content = load_alpha_files(alpha_paths)
    return Briefing(
        text=cleaned_idea,
        objectives=list(objectives),
        alpha_files=alpha_files,
        alpha_content=alpha_content,
    )
