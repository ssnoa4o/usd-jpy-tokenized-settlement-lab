"""Tests for scripts/build_speaker_script.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_speaker_script as bss  # noqa: E402
from build_slides_pdf import split_slides  # noqa: E402

SLIDES = ROOT / "presentation" / "slides.md"

SAMPLE = """# One
- bullet one
<!-- notes: First notes here. -->
---
# Prototype Demonstration
- demo bullet
<!-- notes: Demo words go right here now. -->
---
# No Notes Slide
- plain bullet
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "slides.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_real_slides_notes_appear_exactly_once(tmp_path: Path) -> None:
    text = SLIDES.read_text(encoding="utf-8")
    slides = bss.extract_slides(text)
    assert len(slides) == 12
    out = tmp_path / "s.md"
    bss.build(SLIDES, out)
    content = out.read_text(encoding="utf-8")
    for title, notes in slides:
        assert notes
        assert content.count(notes) == 1


def test_titles_match_split_slides() -> None:
    text = SLIDES.read_text(encoding="utf-8")
    bodies = split_slides(text)
    assert [t for t, _ in bss.extract_slides(text)] == [
        bss._title_of(b) for b in bodies
    ]


def test_notes_text_is_unaltered() -> None:
    slides = bss.extract_slides(SAMPLE)
    assert slides[0][1] == "First notes here."


def test_no_notes_case(tmp_path: Path) -> None:
    out = tmp_path / "o.md"
    bss.build(_write(tmp_path, SAMPLE), out)
    content = out.read_text(encoding="utf-8")
    assert "## 03 No Notes Slide\n\n(no notes)" in content
    assert bss.count_words("") == 0


def test_word_counts_and_cumulative(tmp_path: Path) -> None:
    n, words = bss.build(_write(tmp_path, SAMPLE), tmp_path / "o.md")
    assert (n, words) == (3, 3 + 6)
    content = (tmp_path / "o.md").read_text(encoding="utf-8")
    assert "| 01 | One | 3 | 0.0 | 0.0 |" in content
    assert "| 02 | Prototype Demonstration | 6 | 0.0 | 0.1 |" in content
    assert "Total: 9 words" in content


def test_demo_exclusion_line(tmp_path: Path) -> None:
    out = tmp_path / "o.md"
    bss.build(_write(tmp_path, SAMPLE), out)
    content = out.read_text(encoding="utf-8")
    assert "Total excluding the demo slide: 3 words" in content
    assert "Live demo itself: about 3 minutes, see presentation/demo_script.md." in content


def test_overwrite_guard(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = _write(tmp_path, SAMPLE)
    out = tmp_path / "o.md"
    out.write_text("old", encoding="utf-8")
    assert bss.main(["--slides", str(src), "--out", str(out)]) == 1
    assert "--force" in capsys.readouterr().err
    assert out.read_text(encoding="utf-8") == "old"
    assert bss.main(["--slides", str(src), "--out", str(out), "--force"]) == 0
    assert out.read_text(encoding="utf-8").startswith(bss.HEADER)
    assert "Wrote" in capsys.readouterr().out


def test_notes_do_not_leak_body_text(tmp_path: Path) -> None:
    out = tmp_path / "o.md"
    bss.build(_write(tmp_path, SAMPLE), out)
    content = out.read_text(encoding="utf-8")
    assert "bullet one" not in content
    assert "demo bullet" not in content


def test_fence_and_empty_slide_alignment() -> None:
    text = (
        "# A\n```\n---\n<!-- notes: not a note -->\n```\n<!-- notes: real -->\n"
        "---\n\n---\n# B\n<!-- notes: bee -->\n"
    )
    assert bss.extract_slides(text) == [("A", "real"), ("B", "bee")]


def test_comment_only_slide_with_notes_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = "# A\n<!-- notes: x -->\n---\n<!-- notes: orphan -->\n---\n# B\n"
    with pytest.raises(ValueError, match="Slide 2 has notes"):
        bss.extract_slides(text)
    src = _write(tmp_path, text)
    assert bss.main(["--slides", str(src), "--out", str(tmp_path / "o.md")]) == 1
    assert "Slide 2" in capsys.readouterr().err


def test_two_notes_in_one_slide_are_joined() -> None:
    text = "# A\n<!-- notes: first -->\ntext\n<!-- notes: second -->\n"
    assert bss.extract_slides(text) == [("A", "first\n\nsecond")]


def test_non_notes_comment_is_ignored() -> None:
    text = "# A\n<!-- other: hidden -->\n<!-- notes: spoken -->\n"
    assert bss.extract_slides(text) == [("A", "spoken")]
    assert bss.extract_slides("# A\n<!-- other: hidden -->\n") == [("A", "")]


def test_multiline_notes_comment() -> None:
    text = "# A\n<!-- notes: line one\nline two -->\n"
    assert bss.extract_slides(text) == [("A", "line one\nline two")]


def test_failed_write_leaves_no_tmp_and_keeps_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = _write(tmp_path, SAMPLE)
    out = tmp_path / "o.md"
    out.write_text("old", encoding="utf-8")

    def boom(slides: object) -> str:
        raise RuntimeError("render failed")

    monkeypatch.setattr(bss, "render", boom)
    with pytest.raises(RuntimeError):
        bss.build(src, out, force=True)
    assert out.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_goes_through_tmp_and_os_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[Path, Path]] = []
    real_replace = bss.os.replace

    def spy(a: Path, b: Path) -> None:
        assert Path(a).exists() and Path(a) != Path(b)  # temp file was written
        calls.append((Path(a), Path(b)))
        real_replace(a, b)

    monkeypatch.setattr(bss.os, "replace", spy)
    out = tmp_path / "o.md"
    bss.build(_write(tmp_path, SAMPLE), out)
    assert len(calls) == 1 and calls[0][1] == out
    assert not calls[0][0].exists()


def test_failed_replace_keeps_old_file_and_cleans_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "o.md"
    out.write_text("old", encoding="utf-8")

    def broken(a: object, b: object) -> None:
        raise OSError("disk error")

    monkeypatch.setattr(bss.os, "replace", broken)
    with pytest.raises(OSError):
        bss.build(_write(tmp_path, SAMPLE), out, force=True)
    assert out.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob("*.tmp")) == []


def _words(n: int) -> str:
    return " ".join(["w"] * n)


def test_words_per_minute_constant() -> None:
    assert bss.WORDS_PER_MINUTE == 150
    text = (f"# A\n<!-- notes: {_words(150)} -->\n---\n"
            f"# Prototype Demonstration\n<!-- notes: {_words(300)} -->\n")
    content = bss.render(bss.extract_slides(text))
    assert "| 01 | A | 150 | 1.0 | 1.0 |" in content
    assert "| 02 | Prototype Demonstration | 300 | 2.0 | 3.0 |" in content
    assert "Total: 450 words, ~3.0 min." in content
    assert "Total excluding the demo slide: 150 words, ~1.0 min." in content


def test_cumulative_is_rounded_from_running_total() -> None:
    text = "".join(f"# S{i}\n<!-- notes: {_words(35)} -->\n---\n" for i in range(3))
    content = bss.render(bss.extract_slides(text))
    assert "| 01 | S0 | 35 | 0.2 | 0.2 |" in content
    assert "| 02 | S1 | 35 | 0.2 | 0.5 |" in content
    assert "| 03 | S2 | 35 | 0.2 | 0.7 |" in content
    assert "may differ by 0.1" in content


def test_out_same_as_slides_is_refused_even_with_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write(tmp_path, SAMPLE)
    assert bss.main(["--slides", str(src), "--out", str(src), "--force"]) == 1
    assert "same file" in capsys.readouterr().err
    assert src.read_text(encoding="utf-8") == SAMPLE


def test_title_skips_code_fences() -> None:
    body = "```\n# not a title\n```\n# Real Title\n"
    assert bss._title_of(body) == "Real Title"
    assert bss._title_of("```\n# only in fence\n```") == "Untitled"


def test_missing_demo_slide_warns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write(tmp_path, "# A\n<!-- notes: hi there -->\n")
    assert bss.main(["--slides", str(src), "--out", str(tmp_path / "o.md")]) == 0
    assert "WARNING" in capsys.readouterr().err


def test_two_demo_slides_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = "# Prototype Demonstration\nx\n---\n# Prototype Demonstration\ny\n"
    src = _write(tmp_path, text)
    assert bss.main(["--slides", str(src), "--out", str(tmp_path / "o.md")]) == 1
    assert "expected one" in capsys.readouterr().err


def test_unclosed_comment_same_error_as_pdf_builder() -> None:
    text = "# A\n<!-- notes: never closed\n"
    with pytest.raises(ValueError) as pdf_err:
        split_slides(text)
    with pytest.raises(ValueError) as my_err:
        bss.extract_slides(text)
    assert str(my_err.value) == str(pdf_err.value)


def test_cli_reports_parse_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = _write(tmp_path, "# A\n<!-- notes: open\n")
    assert bss.main(["--slides", str(src), "--out", str(tmp_path / "o.md")]) == 1
    assert "Unclosed HTML comment" in capsys.readouterr().err
