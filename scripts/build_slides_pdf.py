"""Build presentation/slides.pdf (16:9) from presentation/slides.md, offline.

Slide syntax rules:
- `---` on its own line (trailing spaces allowed) is the ONLY slide separator.
  `***` and `----` are not separators. A setext heading (`text` followed by
  `---`) IS treated as a separator, so avoid that style.
- A separator inside a fenced code block (``` or ~~~) does not split.
- Speaker notes are HTML comments (<!-- notes: ... -->) and are removed. Fence
  markers inside a comment are ignored, and `<!--` inside a fence is ignored.
  Outside fences every `<!--` starts a comment, so do not write `<!--` in
  slide text (not even in inline code). An unclosed comment is an error.
- Empty or comment-only slides are dropped (not counted, not printed).
- The build fails if a slide overflows vertically or horizontally, or if its
  content overlaps the footer. The page count is checked as a second guard.

Usage:
    python scripts/build_slides_pdf.py [--input presentation/slides.md]
        [--output presentation/slides.pdf] [--force]
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import html
import os
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_report_pdf import (  # noqa: E402
    _IMG_TAG_RE,
    CHROME_HELP,
    _rewrite_img_tag,
    count_pdf_pages,
)
from src.figures import MODEL_COLORS  # noqa: E402

FOOTER_LEFT = "Independent research prototype · synthetic data"
EXTENSIONS = ["tables", "fenced_code", "attr_list", "md_in_html"]
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")

CSS = f"""
@page {{ size: 13.333in 7.5in; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 20pt;
        line-height: 1.3; color: #222; }}
.slide {{ position: relative; width: 13.333in; height: 7.5in;
          padding: 0.5in 0.7in; overflow: visible; background: #fff;
          break-after: page; page-break-after: always; }}
.slide:last-child {{ break-after: auto; page-break-after: auto; }}
h1 {{ font-size: 30pt; color: #1f3a5f; margin: 0 0 0.25in 0;
      padding-bottom: 6px; border-bottom: 1.5px solid #1f3a5f; }}
h2, h3 {{ color: #1f3a5f; margin: 0.15in 0 0.08in 0; }}
h2 {{ font-size: 22pt; }}
h3 {{ font-size: 19pt; }}
p {{ margin: 0.08in 0; }}
ul, ol {{ margin: 0.08in 0; padding-left: 0.35in; }}
li {{ margin: 0.05in 0; }}
table {{ border-collapse: collapse; font-size: 16pt; margin: 0.1in 0; }}
th, td {{ border: 1px solid #999; padding: 4px 10px; text-align: left; }}
th {{ background: #e8ecf2; color: #1f3a5f; }}
.fig {{ max-height: 4.3in; max-width: 100%; display: block; margin: 0 auto; }}
em {{ font-size: 11pt; color: #666; }}
pre {{ background: #f3f4f6; border: 1px solid #ccc; padding: 8px;
       font-size: 12pt; white-space: pre-wrap; }}
code {{ font-family: Menlo, Consolas, monospace; font-size: 0.9em; }}
.cols {{ display: flex; gap: 0.4in; }}
.cols > * {{ flex: 1; min-width: 0; }}
.cols.figure {{ align-items: flex-start; }}
.cols.figure > :first-child {{ flex: 0 0 7.6in; }}
.cols.figure .fig {{ width: 100%; max-height: none; }}
.cols.figure > :last-child {{ font-size: 16pt; }}
.model-a {{ color: {MODEL_COLORS['sequential']}; font-weight: bold; }}
.model-b {{ color: {MODEL_COLORS['prefunded']}; font-weight: bold; }}
.model-c {{ color: {MODEL_COLORS['atomic']}; font-weight: bold; }}
.title-slide {{ display: flex; flex-direction: column; justify-content: center; }}
.title-slide h1 {{ font-size: 40pt; }}
.slide-footer {{ position: absolute; left: 0.7in; right: 0.7in; bottom: 0.2in;
                 display: flex; justify-content: space-between;
                 font-size: 10pt; color: #666; }}
"""


def _fence_closes(line: str, fence: str) -> bool:
    """Return True if `line` closes a fence opened with `fence` (CommonMark)."""
    m = re.fullmatch(r" {0,3}(`+|~+)[ \t]*", line)
    return bool(m) and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence)


def _strip_comments_in_line(line: str) -> tuple[str, bool]:
    """Remove complete comments from a line; return (text, comment_left_open)."""
    out = ""
    pos = 0
    while True:
        start = line.find("<!--", pos)
        if start < 0:
            return out + line[pos:], False
        end = line.find("-->", start + 4)
        if end < 0:
            return out + line[pos:start], True
        out += line[pos:start]
        pos = end + 3


def split_slides(text: str) -> list[str]:
    """Split Markdown into slides; notes are removed in the same single pass."""
    slides: list[list[str]] = [[]]
    fence: str | None = None  # the opening fence text, e.g. "```"
    comment_line = 0  # line number where the open comment started (0 = none)
    for number, raw in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        line = raw
        if comment_line:
            end = line.find("-->")
            if end < 0:
                continue  # still inside a comment: drop the line
            line = line[end + 3 :]
            comment_line = 0
        elif fence is not None:
            if _fence_closes(line, fence):
                fence = None
            slides[-1].append(line)
            continue
        else:
            m = _FENCE_OPEN_RE.match(line)
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                fence = m.group(1)
                slides[-1].append(line)
                continue
        line, still_open = _strip_comments_in_line(line)
        if still_open:
            comment_line = number
        if re.fullmatch(r"---[ \t]*", line):
            slides.append([])
        else:
            slides[-1].append(line)
    if comment_line:
        raise ValueError(f"Unclosed HTML comment starting on line {comment_line}")
    bodies = ["\n".join(s).strip() for s in slides]
    return [b for b in bodies if b]


def slide_to_html(body: str, number: int, total: int, base_dir: Path) -> str:
    """Render one slide's Markdown as a <section> with a footer."""
    inner = markdown.markdown(body, extensions=EXTENSIONS)
    inner = _IMG_TAG_RE.sub(lambda m: _rewrite_img_tag(m.group(0), base_dir), inner)
    cls = "slide title-slide" if number == 1 else "slide"
    footer = (
        f'<div class="slide-footer"><span>{html.escape(FOOTER_LEFT)}</span>'
        f"<span>{number} / {total}</span></div>"
    )
    return f'<section class="{cls}" id="slide-{number}">{inner}{footer}</section>'


def markdown_to_html(text: str, base_dir: Path) -> str:
    """Convert slide Markdown to a full HTML page (images inlined)."""
    slides = split_slides(text)
    total = len(slides)
    sections = "".join(
        slide_to_html(s, i, total, base_dir) for i, s in enumerate(slides, 1)
    )
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<style>{CSS}</style></head><body>{sections}</body></html>"
    )


OVERFLOW_JS = """
(async () => {
  await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
  const TOL = 1;
  const out = {vertical: [], horizontal: [], footer: []};
  document.querySelectorAll('section.slide').forEach((s, idx) => {
    const n = idx + 1;
    const r = s.getBoundingClientRect();
    const footer = s.querySelector('.slide-footer');
    const fTop = footer ? footer.getBoundingClientRect().top : Infinity;
    let v = s.scrollHeight > s.clientHeight + TOL;
    let h = s.scrollWidth > s.clientWidth + TOL;
    let f = false;
    s.querySelectorAll('*').forEach(el => {
      const b = el.getBoundingClientRect();
      if (b.width === 0 && b.height === 0) return;
      if (b.right > r.right + TOL) h = true;
      if (b.bottom > r.bottom + TOL) v = true;
      if (footer && !footer.contains(el) && b.bottom > fTop + TOL) f = true;
    });
    if (v) out.vertical.push(n);
    if (h) out.horizontal.push(n);
    if (f) out.footer.push(n);
  });
  return JSON.stringify(out);
})()
"""


async def _print_pdf(page_html: str) -> tuple[bytes, dict[str, list[int]]]:
    """Print the HTML to PDF; also return slide numbers with layout problems."""
    import json

    from choreographer import Browser

    async with Browser(headless=True) as browser:
        tab = await browser.create_tab("about:blank")
        await tab.send_command("Page.enable")
        tree = await tab.send_command("Page.getFrameTree")
        frame_id = tree["result"]["frameTree"]["frame"]["id"]
        await tab.send_command(
            "Page.setDocumentContent", {"frameId": frame_id, "html": page_html}
        )
        ev = await tab.send_command(
            "Runtime.evaluate",
            {"expression": OVERFLOW_JS, "returnByValue": True, "awaitPromise": True},
        )
        problems = json.loads(ev["result"]["result"]["value"])
        res = await tab.send_command(
            "Page.printToPDF",
            {
                "preferCSSPageSize": True,
                "printBackground": True,
                "displayHeaderFooter": False,
            },
        )
    return base64.b64decode(res["result"]["data"]), problems


def html_to_pdf(page_html: str, n_slides: int) -> bytes:
    """Render HTML to PDF; raise on overflow or footer overlap."""
    from choreographer.browsers import ChromeNotFoundError

    try:
        pdf, problems = asyncio.run(
            asyncio.wait_for(_print_pdf(page_html), timeout=90)
        )
    except ChromeNotFoundError as err:
        raise RuntimeError(CHROME_HELP) from err
    except TimeoutError as err:
        raise RuntimeError("Chrome did not respond within 90 seconds.") from err
    pages = count_pdf_pages(pdf)
    labels = {"vertical": "vertical overflow", "horizontal": "horizontal overflow",
              "footer": "footer overlap"}
    details = [f"{labels[k]}: slides {v}" for k, v in problems.items() if v]
    if details or pages != n_slides:
        extra = f" ({'; '.join(details)})" if details else ""
        raise RuntimeError(
            f"content overflowed: {n_slides} slides but {pages} pages{extra}"
        )
    return pdf


def build(input_path: Path, output_path: Path, force: bool = False) -> int:
    """Build the PDF and return its page count."""
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} exists. Use --force to overwrite.")
    if not input_path.is_file():
        raise FileNotFoundError(f"Input not found: {input_path}")
    text = input_path.read_text(encoding="utf-8")
    n_slides = len(split_slides(text))
    if n_slides == 0:
        raise ValueError("No slides found in the input.")
    page = markdown_to_html(text, input_path.resolve().parent)
    pdf = html_to_pdf(page, n_slides)
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
    ap.add_argument("--input", default="presentation/slides.md")
    ap.add_argument("--output", default="presentation/slides.pdf")
    ap.add_argument("--force", action="store_true", help="overwrite output")
    args = ap.parse_args(argv)
    try:
        pages = build(Path(args.input), Path(args.output), args.force)
    except Exception as err:
        if os.environ.get("DEBUG"):
            raise
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} ({pages} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
