"""Tests for scripts/build_report_pdf.py (Markdown -> PDF)."""
from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_report_pdf.py"
spec = importlib.util.spec_from_file_location("build_report_pdf", SCRIPT)
brp = importlib.util.module_from_spec(spec)
sys.modules["build_report_pdf"] = brp
spec.loader.exec_module(brp)

# 1x1 transparent PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
    "60e6kgAAAABJRU5ErkJggg=="
)
MD = "# T\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n![fig](../figs/x.png)\n"


def _make_tree(tmp_path: Path) -> Path:
    """Create tmp/research/report.md and tmp/figs/x.png; return the md path."""
    (tmp_path / "research").mkdir()
    (tmp_path / "figs").mkdir()
    (tmp_path / "figs" / "x.png").write_bytes(PNG)
    md = tmp_path / "research" / "report.md"
    md.write_text(MD, encoding="utf-8")
    return md


def _chrome_available() -> bool:
    try:
        from choreographer.browsers import Chromium

        return bool(Chromium.find_browser(skip_local=False))
    except Exception:
        return False


def test_html_has_table_and_inlined_image(tmp_path: Path) -> None:
    md = _make_tree(tmp_path)
    out = brp.markdown_to_html(MD, md.parent)
    assert "<table>" in out
    assert "data:image/png;base64," in out
    assert "../figs/x.png" not in out


def test_missing_image_raises(tmp_path: Path) -> None:
    (tmp_path / "research").mkdir()
    with pytest.raises(FileNotFoundError, match="Image not found") as info:
        brp.markdown_to_html(MD, tmp_path / "research")
    assert str(tmp_path.resolve() / "figs" / "x.png") in str(info.value)


def _html_for(tmp_path: Path, snippet: str) -> str:
    md = _make_tree(tmp_path)
    return brp.markdown_to_html(snippet, md.parent)


@pytest.mark.parametrize(
    "snippet",
    [
        "<img src='../figs/x.png'>",
        "<img src=../figs/x.png>",
        '<IMG SRC="../figs/x.png" ALT="a">',
        '![t](../figs/x.png "a title")',
        "<img alt='a>b' src='../figs/x.png'>",
    ],
)
def test_image_forms_are_inlined(tmp_path: Path, snippet: str) -> None:
    out = _html_for(tmp_path, snippet)
    assert "data:image/png;base64," in out
    assert "figs/x.png" not in out


def test_percent_encoded_path(tmp_path: Path) -> None:
    md = _make_tree(tmp_path)
    (tmp_path / "figs" / "my fig.png").write_bytes(PNG)
    out = brp.markdown_to_html("![a](../figs/my%20fig.png)", md.parent)
    assert "data:image/png;base64," in out


def test_missing_image_in_raw_html_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _html_for(tmp_path, "<img src='../figs/nope.png'>")


@pytest.mark.parametrize(
    "url",
    ["http://example.com/a.png", "HTTPS://example.com/a.png", "//example.com/a.png"],
)
def test_remote_image_rejected(tmp_path: Path, url: str) -> None:
    with pytest.raises(ValueError, match="Remote image"):
        _html_for(tmp_path, f"![r]({url})")


def test_data_uri_passes(tmp_path: Path) -> None:
    out = _html_for(tmp_path, "<img src='data:image/png;base64,AAAA'>")
    assert "data:image/png;base64,AAAA" in out


def test_main_exit_1_on_missing_image(tmp_path: Path, capsys) -> None:
    md = tmp_path / "r.md"
    md.write_text("![x](nope.png)", encoding="utf-8")
    out = tmp_path / "o.pdf"
    assert brp.main(["--input", str(md), "--output", str(out)]) == 1
    assert "ERROR: Image not found" in capsys.readouterr().err
    assert not out.exists()


def test_failed_build_keeps_old_pdf_with_force(tmp_path: Path) -> None:
    md = tmp_path / "r.md"
    md.write_text("![x](nope.png)", encoding="utf-8")
    out = tmp_path / "o.pdf"
    out.write_bytes(b"old")
    assert brp.main(["--input", str(md), "--output", str(out), "--force"]) == 1
    assert out.read_bytes() == b"old"


def test_unexpected_error_is_reported(tmp_path: Path, monkeypatch, capsys) -> None:
    md = _make_tree(tmp_path)
    monkeypatch.setattr(brp, "html_to_pdf", lambda _h: 1 / 0)
    assert brp.main(["--input", str(md), "--output", str(tmp_path / "o.pdf")]) == 1
    assert "ERROR:" in capsys.readouterr().err


def test_write_failure_keeps_old_pdf(tmp_path: Path, monkeypatch) -> None:
    md = _make_tree(tmp_path)
    out = tmp_path / "o.pdf"
    out.write_bytes(b"old")
    monkeypatch.setattr(brp, "html_to_pdf", lambda _h: b"%PDF new")
    monkeypatch.setattr(brp.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("x")))
    assert brp.main(["--input", str(md), "--output", str(out), "--force"]) == 1
    assert out.read_bytes() == b"old"
    assert not list(tmp_path.glob("*.tmp"))


def test_refuses_overwrite_without_force(tmp_path: Path, capsys) -> None:
    md = _make_tree(tmp_path)
    out = tmp_path / "out.pdf"
    out.write_bytes(b"old")
    code = brp.main(["--input", str(md), "--output", str(out)])
    assert code == 1
    assert out.read_bytes() == b"old"
    assert "--force" in capsys.readouterr().err


def test_count_pdf_pages_ignores_pages_node() -> None:
    fake = b"/Type /Pages /Count 2 /Type /Page /Type/Page"
    assert brp.count_pdf_pages(fake) == 2


@pytest.mark.skipif(not _chrome_available(), reason="Chrome not found; run .venv/bin/kaleido_get_chrome")
def test_end_to_end_pdf(tmp_path: Path, capsys) -> None:
    md = _make_tree(tmp_path)
    out = tmp_path / "report.pdf"
    assert brp.main(["--input", str(md), "--output", str(out)]) == 0
    assert out.read_bytes().startswith(b"%PDF")
    assert "pages)" in capsys.readouterr().out
    assert brp.count_pdf_pages(out.read_bytes()) >= 1
