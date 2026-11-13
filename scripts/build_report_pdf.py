"""Build research/report.pdf from research/report.md, fully offline.

Steps: Markdown -> HTML (with print stylesheet, images inlined as base64)
-> headless Chrome (from kaleido/choreographer) -> Page.printToPDF.

Usage:
    python scripts/build_report_pdf.py [--input research/report.md]
        [--output research/report.pdf] [--force]
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import html
import mimetypes
import re
import os
import sys
import urllib.parse
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
CHROME_HELP = "Chrome was not found. Run: .venv/bin/kaleido_get_chrome"

CSS = """
@page { size: A4; margin: 1.8cm; }
html { font-family: Georgia, 'Times New Roman', serif; font-size: 10pt;
       line-height: 1.35; color: #222; }
h1, h2, h3, h4 { font-family: Helvetica, Arial, sans-serif; color: #1f3a5f;
       page-break-after: avoid; break-after: avoid; }
h1 { font-size: 20pt; border-bottom: 2px solid #1f3a5f; padding-bottom: 4px; }
h2 { font-size: 14pt; margin-top: 1.4em; }
h3 { font-size: 11.5pt; }
p, li { orphans: 3; widows: 3; }
table { border-collapse: collapse; width: 100%; table-layout: auto;
        font-size: 8.5pt; margin: 0.8em 0; page-break-inside: avoid; }
th, td { border: 0.5px solid #999; padding: 3px 5px; text-align: left;
         vertical-align: top; overflow-wrap: anywhere; word-break: break-word; }
th { background: #e8ecf2; color: #1f3a5f; }
img { max-width: 80%; height: auto; page-break-inside: avoid;
      break-inside: avoid; display: block; margin: 0.6em auto; }
pre { background: #f3f4f6; border: 0.5px solid #ccc; padding: 6px;
      font-size: 8.5pt; white-space: pre-wrap; overflow-wrap: anywhere; }
code { font-family: Menlo, Consolas, monospace; font-size: 9pt; }
blockquote { border-left: 3px solid #1f3a5f; margin-left: 0; padding-left: 10px;
             color: #555; }
a { color: #1f3a5f; }
"""

FOOTER = (
    '<div style="font-size:8px;width:100%;text-align:center;color:#666;">'
    '<span class="pageNumber"></span> / <span class="totalPages"></span></div>'
)

# An <img ...> tag (quotes may contain ">"), and one attribute inside it.
_IMG_TAG_RE = re.compile(r"<img\b(?:\"[^\"]*\"|'[^']*'|[^'\">])*>", re.IGNORECASE)
_ATTR_RE = re.compile(
    r"""([^\s=/<>"']+)(\s*=\s*)("[^"]*"|'[^']*'|[^\s>"']+)""", re.IGNORECASE
)


def _inline_image(src: str, base_dir: Path) -> str:
    """Return a base64 data URI for a local image; raise if it is missing."""
    src = html.unescape(src.strip())
    lowered = src.lower()
    if lowered.startswith("data:"):
        return src
    if lowered.startswith(("http://", "https://", "//")):
        raise ValueError(
            f"Remote image not allowed (the build is offline): {src}. "
            "Download it into results/figures/ and use a relative path."
        )
    path = (base_dir / urllib.parse.unquote(src)).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {src} (looked at {path})")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _rewrite_img_tag(tag: str, base_dir: Path) -> str:
    """Replace the src attribute of one <img> tag with an inlined data URI."""

    def fix(m: re.Match) -> str:
        if m.group(1).lower() != "src":
            return m.group(0)
        value = m.group(3).strip("\"'")
        return f'{m.group(1)}{m.group(2)}"{_inline_image(value, base_dir)}"'

    return _ATTR_RE.sub(fix, tag)


def markdown_to_html(text: str, base_dir: Path) -> str:
    """Convert Markdown text to a full HTML page with images inlined."""
    body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "toc", "attr_list"]
    )
    body = _IMG_TAG_RE.sub(lambda m: _rewrite_img_tag(m.group(0), base_dir), body)
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<style>{CSS}</style></head><body>{body}</body></html>"
    )


async def _print_pdf(page_html: str) -> bytes:
    """Open headless Chrome, load the HTML and print it to PDF bytes."""
    from choreographer import Browser

    async with Browser(headless=True) as browser:
        tab = await browser.create_tab("about:blank")
        await tab.send_command("Page.enable")
        tree = await tab.send_command("Page.getFrameTree")
        frame_id = tree["result"]["frameTree"]["frame"]["id"]
        await tab.send_command(
            "Page.setDocumentContent", {"frameId": frame_id, "html": page_html}
        )
        res = await tab.send_command(
            "Page.printToPDF",
            {
                "preferCSSPageSize": True,
                "printBackground": True,
                "displayHeaderFooter": True,
                "headerTemplate": "<div></div>",
                "footerTemplate": FOOTER,
            },
        )
    return base64.b64decode(res["result"]["data"])


def html_to_pdf(page_html: str) -> bytes:
    """Render HTML to PDF bytes with headless Chrome (Page.printToPDF)."""
    from choreographer.browsers import ChromeNotFoundError

    try:
        return asyncio.run(asyncio.wait_for(_print_pdf(page_html), timeout=90))
    except ChromeNotFoundError as err:
        raise RuntimeError(CHROME_HELP) from err
    except TimeoutError as err:
        raise RuntimeError("Chrome did not respond within 90 seconds.") from err


def count_pdf_pages(pdf: bytes) -> int:
    """Count /Type /Page objects (not /Pages) in raw PDF bytes."""
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf))


def build(input_path: Path, output_path: Path, force: bool = False) -> int:
    """Build the PDF and return its page count."""
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} exists. Use --force to overwrite.")
    if not input_path.is_file():
        raise FileNotFoundError(f"Input not found: {input_path}")
    page = markdown_to_html(
        input_path.read_text(encoding="utf-8"), input_path.resolve().parent
    )
    pdf = html_to_pdf(page)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_name(output_path.name + ".tmp")
    try:
        tmp.write_bytes(pdf)
        os.replace(tmp, output_path)  # old PDF stays intact if writing fails
    finally:
        tmp.unlink(missing_ok=True)
    return count_pdf_pages(pdf)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", default="research/report.md")
    ap.add_argument("--output", default="research/report.pdf")
    ap.add_argument("--force", action="store_true", help="overwrite output")
    args = ap.parse_args(argv)
    try:
        pages = build(Path(args.input), Path(args.output), args.force)
    except Exception as err:  # keep the message short for beginners
        if os.environ.get("DEBUG"):
            raise
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} ({pages} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
