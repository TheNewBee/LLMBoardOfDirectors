from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from boardroom.briefing.io import SUPPORTED_ALPHA_SUFFIXES, build_briefing, load_alpha_files


def test_load_alpha_files_empty() -> None:
    files, content = load_alpha_files([])
    assert files == []
    assert content == {}


def test_load_alpha_files_reads_supported_types(tmp_path: Path) -> None:
    p_txt = tmp_path / "a.txt"
    p_txt.write_text("hello", encoding="utf-8")
    p_md = tmp_path / "b.md"
    p_md.write_text("# x", encoding="utf-8")
    p_json = tmp_path / "c.json"
    p_json.write_text('{"k":1}', encoding="utf-8")

    files, content = load_alpha_files([p_txt, p_md, p_json])
    assert len(files) == 3
    assert content[p_txt.resolve().as_posix()] == "hello"
    assert content[p_md.resolve().as_posix()] == "# x"
    assert content[p_json.resolve().as_posix()] == '{"k":1}'


def test_load_alpha_files_rejects_unsupported_suffix(tmp_path: Path) -> None:
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError, match="Unsupported Alpha file type"):
        load_alpha_files([p])


def test_load_alpha_files_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"
    with pytest.raises(FileNotFoundError):
        load_alpha_files([missing])


def test_load_alpha_files_deduplicates_same_path(tmp_path: Path) -> None:
    p = tmp_path / "one.txt"
    p.write_text("z", encoding="utf-8")
    files, content = load_alpha_files([p, p])
    assert len(files) == 1
    assert len(content) == 1


def test_build_briefing_requires_nonblank_idea() -> None:
    with pytest.raises(ValidationError):
        build_briefing("   ", objectives=["Do a thing"])


def test_build_briefing_requires_at_least_one_objective() -> None:
    with pytest.raises(ValidationError):
        build_briefing("Ship Q2", objectives=[])


def test_build_briefing_strips_objectives() -> None:
    b = build_briefing("Idea", objectives=["  first  ", "", "second"])
    assert b.objectives == ["first", "second"]


def test_build_briefing_with_alpha_files(tmp_path: Path) -> None:
    f = tmp_path / "note.md"
    f.write_text("body", encoding="utf-8")
    b = build_briefing("Pitch", objectives=["Validate"], alpha_paths=[f])
    assert b.text == "Pitch"
    assert b.alpha_content[f.resolve().as_posix()] == "body"
    assert b.alpha_files[0] == f.resolve()


def test_supported_suffix_set_is_phase1_scope() -> None:
    assert ".pdf" not in SUPPORTED_ALPHA_SUFFIXES
    assert ".txt" in SUPPORTED_ALPHA_SUFFIXES
