"""Tests for scripts/build_slides_pdf.py (slides.md -> 16:9 PDF)."""
from __future__ import annotations

import base64
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_slides_pdf.py"
spec = importlib.util.spec_from_file_location("build_slides_pdf", SCRIPT)
bsp = importlib.util.module_from_spec(spec)
sys.modules["build_slides_pdf"] = bsp
spec.loader.exec_module(bsp)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
    "60e6kgAAAABJRU5ErkJggg=="
)
FIXTURE = (
    "# Title\n\nHello\n\n<!-- notes: SECRET-NOTE -->\n\n---\n\n"
    "# Two\n\n- a\n- b\n\n---\n\n# Three\n\n"
    '<div class="cols" markdown="1">\n\nleft\n\nright\n\n</div>\n'
)


def _chrome_available() -> bool:
    try:
        from choreographer.browsers import Chromium

        return bool(Chromium.find_browser(skip_local=False))
    except Exception:
        return False


needs_chrome = pytest.mark.skipif(
    not _chrome_available(), reason="Chrome not found; run .venv/bin/kaleido_get_chrome"
)


def test_split_count() -> None:
    assert len(bsp.split_slides(FIXTURE)) == 3


def test_dashes_in_code_fence_do_not_split() -> None:
    text = "# A\n\n```\nx\n---\ny\n```\n\n---\n\n# B\n"
    slides = bsp.split_slides(text)
    assert len(slides) == 2
    assert "---" in slides[0]


def test_notes_absent_from_html(tmp_path: Path) -> None:
    out = bsp.markdown_to_html(FIXTURE, tmp_path)
    assert "SECRET-NOTE" not in out
    assert "notes:" not in out


def test_multiline_note_with_dashes_is_removed(tmp_path: Path) -> None:
    text = "# A\n\n<!-- notes: hidden\n---\nmore -->\n\n---\n\n# B\n"
    assert len(bsp.split_slides(text)) == 2
    assert "hidden" not in bsp.markdown_to_html(text, tmp_path)


def test_image_inlined(tmp_path: Path) -> None:
    (tmp_path / "x.png").write_bytes(PNG)
    out = bsp.markdown_to_html("# A\n\n![a](x.png){.fig}\n", tmp_path)
    assert "data:image/png;base64," in out
    assert 'class="fig"' in out


def test_remote_image_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Remote image"):
        bsp.markdown_to_html("# A\n\n![r](https://example.com/a.png)\n", tmp_path)


def test_first_slide_is_title_slide(tmp_path: Path) -> None:
    out = bsp.markdown_to_html(FIXTURE, tmp_path)
    assert '<section class="slide title-slide" id="slide-1">' in out
    assert '<section class="slide" id="slide-2">' in out
    assert out.count("title-slide\" id") == 1


def test_footer_numbering(tmp_path: Path) -> None:
    out = bsp.markdown_to_html(FIXTURE, tmp_path)
    for n in (1, 2, 3):
        assert f"<span>{n} / 3</span>" in out
    assert "Independent research prototype" in out


def test_md_in_html_columns(tmp_path: Path) -> None:
    out = bsp.markdown_to_html(FIXTURE, tmp_path)
    assert '<div class="cols">' in out
    assert "<p>left</p>" in out


def test_model_colors_match_figures() -> None:
    from src.figures import MODEL_COLORS

    css = bsp.CSS
    assert f".model-a {{ color: {MODEL_COLORS['sequential']}" in css
    assert f".model-b {{ color: {MODEL_COLORS['prefunded']}" in css
    assert f".model-c {{ color: {MODEL_COLORS['atomic']}" in css


def test_refuses_overwrite_without_force(tmp_path: Path, capsys) -> None:
    md = tmp_path / "s.md"
    md.write_text(FIXTURE, encoding="utf-8")
    out = tmp_path / "s.pdf"
    out.write_bytes(b"old")
    assert bsp.main(["--input", str(md), "--output", str(out)]) == 1
    assert out.read_bytes() == b"old"
    assert "--force" in capsys.readouterr().err


@needs_chrome
def test_real_build_page_count_matches_slides(tmp_path: Path, capsys) -> None:
    md = tmp_path / "s.md"
    md.write_text(FIXTURE, encoding="utf-8")
    out = tmp_path / "s.pdf"
    assert bsp.main(["--input", str(md), "--output", str(out)]) == 0
    pdf = out.read_bytes()
    assert pdf.startswith(b"%PDF")
    assert bsp.count_pdf_pages(pdf) == 3
    assert "(3 pages)" in capsys.readouterr().out


def test_unclosed_comment_raises() -> None:
    with pytest.raises(ValueError, match="Unclosed HTML comment starting on line 3"):
        bsp.split_slides("# A\n\n<!-- oops\n---\n# B\n")


def test_dashes_inside_tilde_fence_do_not_split() -> None:
    slides = bsp.split_slides("# A\n\n~~~\nx\n---\ny\n~~~\n\n---\n# B\n")
    assert len(slides) == 2 and "---" in slides[0]


def test_longer_fence_needs_matching_close() -> None:
    text = "# A\n````\n```\n---\n````\n---\n# B"
    assert len(bsp.split_slides(text)) == 2


def test_fence_marker_inside_comment_is_ignored() -> None:
    text = "# A\n<!--\n```\n-->\n---\n# B\n---\n# C"
    assert len(bsp.split_slides(text)) == 3


def test_comment_opener_inside_fence_is_ignored() -> None:
    slides = bsp.split_slides("# A\n```\n<!--\n```\n---\n# B")
    assert len(slides) == 2 and "<!--" in slides[0]


def test_crlf_input_splits_like_lf() -> None:
    assert len(bsp.split_slides(FIXTURE.replace("\n", "\r\n"))) == 3


def test_trailing_and_empty_separators_make_no_empty_slide() -> None:
    assert len(bsp.split_slides("# A\n---\n# B\n---\n")) == 2
    assert len(bsp.split_slides("# A\n---  \n<!-- only note -->\n---\n# B")) == 2


def test_missing_image_raises(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        bsp.markdown_to_html("# A\n\n![m](nope.png)\n", tmp_path)


def test_write_failure_keeps_existing_pdf(tmp_path: Path, monkeypatch) -> None:
    md = tmp_path / "s.md"
    md.write_text("# A\n", encoding="utf-8")
    out = tmp_path / "s.pdf"
    out.write_bytes(b"old")
    monkeypatch.setattr(bsp, "html_to_pdf", lambda page, n: b"%PDF-new")
    monkeypatch.setattr(bsp, "count_pdf_pages", lambda pdf: 1)

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(bsp.os, "replace", boom)
    with pytest.raises(OSError):
        bsp.build(md, out, force=True)
    assert out.read_bytes() == b"old"
    assert not (tmp_path / "s.pdf.tmp").exists()


def _run(tmp_path: Path, body: str, capsys) -> tuple[int, str]:
    """Build `body` with the real Chrome; return (exit code, stderr)."""
    md = tmp_path / "s.md"
    md.write_text(body, encoding="utf-8")
    code = bsp.main(["--input", str(md), "--output", str(tmp_path / "s.pdf")])
    return code, capsys.readouterr().err


# The tests below need Chrome and are skipped when it is missing.
@needs_chrome
def test_vertical_overflow_is_reported(tmp_path: Path, capsys) -> None:
    long_body = "\n".join(f"- line {i}" for i in range(80))
    code, err = _run(tmp_path, f"# A\n\nshort\n\n---\n\n# B\n\n{long_body}\n", capsys)
    assert code == 1
    assert "content overflowed: 2 slides but" in err
    assert "vertical overflow: slides [2]" in err
    assert not (tmp_path / "s.pdf").exists()


@needs_chrome
def test_wide_table_is_horizontal_overflow_only(tmp_path: Path, capsys) -> None:
    """Page count stays equal, so only the JS horizontal check can catch this."""
    cells = " | ".join(f"column-header-{i}" for i in range(12))
    table = f"| {cells} |\n|{'---|' * 12}\n| {cells} |"
    code, err = _run(tmp_path, f"# A\n\n{table}\n\n---\n\n# B\n", capsys)
    assert code == 1
    assert "2 slides but 2 pages" in err
    assert "horizontal overflow: slides [1]" in err


@needs_chrome
def test_absolute_element_is_vertical_overflow_only(tmp_path: Path, capsys) -> None:
    """Element placed below the slide: JS vertical check must catch it."""
    box = '<div style="position:absolute; top:8in; left:0">low</div>'
    code, err = _run(tmp_path, f"# A\n\n{box}\n\n---\n\n# B\n", capsys)
    assert code == 1
    assert "vertical overflow: slides [1]" in err


@needs_chrome
def test_page_count_guard_catches_forced_page_break(tmp_path: Path, capsys) -> None:
    """A forced page break gives extra pages with no overflow: count guard only."""
    brk = '<div style="break-before: page">x</div>'
    code, err = _run(tmp_path, f"# A\n\n---\n\n# B\n\n{brk}\n", capsys)
    assert code == 1
    assert "2 slides but 3 pages" in err


@needs_chrome
def test_footer_overlap_is_reported(tmp_path: Path, capsys) -> None:
    box = '<div style="height: 5.9in">tall</div>'
    code, err = _run(tmp_path, f"# A\n\n---\n\n# B\n\n{box}\n", capsys)
    assert code == 1
    assert "footer overlap: slides [2]" in err
    assert "overflow: slides" not in err


@needs_chrome
def test_pdf_text_has_no_notes_and_crlf_builds(tmp_path: Path, capsys) -> None:
    md = tmp_path / "s.md"
    md.write_bytes(FIXTURE.replace("\n", "\r\n").encode())
    out = tmp_path / "s.pdf"
    assert bsp.main(["--input", str(md), "--output", str(out)]) == 0
    assert bsp.count_pdf_pages(out.read_bytes()) == 3
    exe = shutil.which("pdftotext")
    if exe:  # optional external tool; skip this check when absent
        text = subprocess.run(
            [exe, str(out), "-"], capture_output=True, text=True, check=True
        ).stdout
        assert "Two" in text
        assert "SECRET-NOTE" not in text
