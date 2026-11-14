"""Build presentation/speaker_script.md from the notes in presentation/slides.md.

slides.md stays the single source of the spoken text. Slides are split with
`split_slides` from build_slides_pdf.py; notes are the `<!-- notes: ... -->`
comments, found with the same fence/comment helpers (a cross-check makes sure
both passes see exactly the same slides).

Usage:
    python scripts/build_speaker_script.py [--slides presentation/slides.md]
        [--out presentation/speaker_script.md] [--force]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_slides_pdf import (  # noqa: E402
    _FENCE_OPEN_RE,
    _fence_closes,
    split_slides,
)

WORDS_PER_MINUTE = 150
DEMO_TITLE = "Prototype Demonstration"
HEADER = (
    "Generated from presentation/slides.md by scripts/build_speaker_script.py. "
    "Do not edit by hand; edit the notes in slides.md and rebuild."
)
NO_NOTES = "(no notes)"


def _split_notes(text: str) -> list[tuple[list[str], bool]]:
    """Return, per raw slide, (notes found in its comments, has visible text)."""
    notes: list[list[str]] = [[]]
    has_body: list[bool] = [False]
    fence: str | None = None
    buffer: str | None = None  # text of a comment that is still open
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw
        if buffer is not None:
            end = line.find("-->")
            if end < 0:
                buffer += "\n" + line
                continue
            _add_note(notes[-1], buffer + "\n" + line[:end])
            buffer = None
            line = line[end + 3 :]
        elif fence is not None:
            if _fence_closes(line, fence):
                fence = None
            has_body[-1] = True
            continue
        else:
            m = _FENCE_OPEN_RE.match(line)
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                fence = m.group(1)
                has_body[-1] = True
                continue
        rest = line
        while "<!--" in rest:
            start = rest.find("<!--")
            end = rest.find("-->", start + 4)
            if end < 0:
                buffer = rest[start + 4 :]
                rest = rest[:start]
                break
            _add_note(notes[-1], rest[start + 4 : end])
            rest = rest[:start] + rest[end + 3 :]
        if re.fullmatch(r"---[ \t]*", rest):
            notes.append([])
            has_body.append(False)
        elif rest.strip():
            has_body[-1] = True
    return list(zip(notes, has_body))


def _add_note(target: list[str], comment: str) -> None:
    """Keep the comment only if it starts with `notes:`."""
    body = comment.strip()
    if body.lower().startswith("notes:"):
        target.append(body[len("notes:") :].strip())


def _title_of(body: str) -> str:
    """Return the first `# ` heading of a slide body (outside code fences)."""
    fence: str | None = None
    for line in body.split("\n"):
        if fence is not None:
            if _fence_closes(line, fence):
                fence = None
            continue
        m = _FENCE_OPEN_RE.match(line)
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence = m.group(1)
            continue
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


def extract_slides(text: str) -> list[tuple[str, str]]:
    """Return (title, notes_text) per slide; notes_text is "" if none.

    Raises ValueError on an unclosed comment (same error as the PDF builder)
    or on notes that sit in a slide without visible content.
    """
    bodies = split_slides(text)  # raises on unclosed comment
    kept = []
    for position, (notes, has_body) in enumerate(_split_notes(text), 1):
        if has_body:
            kept.append(notes)
        elif notes:
            raise ValueError(
                f"Slide {position} has notes but no visible content; "
                "its notes would be lost. Add content or move the notes."
            )
    if len(kept) != len(bodies):
        raise ValueError("Internal error: notes and slides are out of step.")
    return [(_title_of(b), "\n\n".join(n)) for b, n in zip(bodies, kept)]


def count_words(notes: str) -> int:
    """Count words by splitting on whitespace."""
    return len(notes.split())


def render(slides: list[tuple[str, str]]) -> str:
    """Build the Markdown speaker script."""
    rows: list[tuple[int, str, int, float, float]] = []
    cumulative = 0
    for i, (title, notes) in enumerate(slides, 1):
        words = count_words(notes)
        cumulative += words
        rows.append((i, title, words, words / WORDS_PER_MINUTE,
                     cumulative / WORDS_PER_MINUTE))
    total_words = cumulative
    demo_words = sum(r[2] for r in rows if r[1] == DEMO_TITLE)
    out = [HEADER, "", "# Speaker Script", "",
           f"Estimated at {WORDS_PER_MINUTE} words per minute.", "",
           "| Slide | Title | Words | Est. min | Cumulative min |",
           "|---|---|---|---|---|"]
    for n, title, words, minutes, cum in rows:
        out.append(f"| {n:02d} | {title} | {words} | {minutes:.1f} | {cum:.1f} |")
    out += ["", f"Total: {total_words} words, "
            f"~{total_words / WORDS_PER_MINUTE:.1f} min.",
            f"Total excluding the demo slide: {total_words - demo_words} words, "
            f"~{(total_words - demo_words) / WORDS_PER_MINUTE:.1f} min.",
            "Est. min is rounded per slide; the cumulative column is rounded "
            "from the running total, so the two may differ by 0.1.",
            "Live demo itself: about 3 minutes, see presentation/demo_script.md.",
            ""]
    for i, (title, notes) in enumerate(slides, 1):
        out += [f"## {i:02d} {title}", "", notes if notes else NO_NOTES, ""]
    return "\n".join(out)


def check_demo_slide(slides: list[tuple[str, str]]) -> None:
    """Warn if no demo slide is found; fail if more than one matches."""
    count = sum(1 for title, _ in slides if title == DEMO_TITLE)
    if count > 1:
        raise ValueError(f"{count} slides are titled {DEMO_TITLE!r}; expected one.")
    if count == 0:
        print(f"WARNING: no slide titled {DEMO_TITLE!r}; "
              "the demo exclusion line equals the total.", file=sys.stderr)


def build(slides_path: Path, out_path: Path, force: bool = False) -> tuple[int, int]:
    """Write the script; return (slide count, total words)."""
    if out_path.resolve() == slides_path.resolve():
        raise ValueError("--out must not be the same file as --slides.")
    if out_path.exists() and not force:
        raise FileExistsError(f"{out_path} exists. Use --force to overwrite.")
    if not slides_path.is_file():
        raise FileNotFoundError(f"Input not found: {slides_path}")
    slides = extract_slides(slides_path.read_text(encoding="utf-8"))
    if not slides:
        raise ValueError("No slides found in the input.")
    check_demo_slide(slides)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    try:
        tmp.write_text(render(slides), encoding="utf-8")
        os.replace(tmp, out_path)
    finally:
        tmp.unlink(missing_ok=True)
    return len(slides), sum(count_words(n) for _, n in slides)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slides", default="presentation/slides.md")
    ap.add_argument("--out", default="presentation/speaker_script.md")
    ap.add_argument("--force", action="store_true", help="overwrite output")
    args = ap.parse_args(argv)
    try:
        n, words = build(Path(args.slides), Path(args.out), args.force)
    except Exception as err:
        if os.environ.get("DEBUG"):
            raise
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"Wrote {args.out} ({n} slides, {words} words, "
          f"~{words / WORDS_PER_MINUTE:.0f} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
