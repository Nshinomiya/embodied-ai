"""CLI helper for the screen-read skill.

Orchestrates the deterministic parts of the pipeline so the skill body
in SKILL.md can stay focused on tool calls (camera capture, OCR, user
interaction). All subcommands emit JSON to stdout and use exit code 0
for success / 1 for failure.

Run with:
    uv run --project screen_read python \\
        .claude/skills/screen-read/scripts/screen_read_helper.py <subcommand> ...
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCREEN_READ_DIR = REPO_ROOT / "screen_read"
sys.path.insert(0, str(SCREEN_READ_DIR))

from merge import MAX_PAGES, best_overlap, merge_pages  # noqa: E402
from preprocess import (  # noqa: E402
    CAPTURE_COOLDOWN_SECONDS,
    measure_blur,
    resize_long_edge,
    strip_exif,
)


def _emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def cmd_preprocess(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        _emit({"ok": False, "error": f"not found: {path}"})
        return 1

    blur = measure_blur(path)
    if blur.is_blurry and not args.force:
        _emit(
            {
                "ok": False,
                "blurry": True,
                "variance": blur.variance,
                "hint": "ピントが甘いので撮り直してください",
            }
        )
        return 0  # not a hard error; orchestrator decides

    strip_exif(path)
    width, height = resize_long_edge(path)
    _emit(
        {
            "ok": True,
            "blurry": blur.is_blurry,
            "variance": blur.variance,
            "size": [width, height],
            "cooldown_seconds": CAPTURE_COOLDOWN_SECONDS,
        }
    )
    return 0


def cmd_same_page(args: argparse.Namespace) -> int:
    """Pixel-difference based "is this the same screen as last shot" check.

    Used as one half of the F-7 dual end-of-session detection. The other
    half is the ``---END---`` marker detected in OCR output by the skill.
    """
    import cv2
    import numpy as np

    a = cv2.imread(args.a, cv2.IMREAD_GRAYSCALE)
    b = cv2.imread(args.b, cv2.IMREAD_GRAYSCALE)
    if a is None or b is None:
        _emit({"ok": False, "error": "failed to read one of the images"})
        return 1
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    diff = float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean())
    _emit({"ok": True, "mean_abs_diff": diff, "is_same": diff < args.threshold})
    return 0


def _list_page_files(session_dir: Path) -> list[Path]:
    return sorted(session_dir.glob("page-*.json"), key=lambda p: int(p.stem.split("-")[1]))


def cmd_save_page(args: argparse.Namespace) -> int:
    """Persist a single page's OCR result for resume + merge."""
    session_dir = Path(args.session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    if args.page > MAX_PAGES:
        _emit({"ok": False, "error": f"page {args.page} exceeds MAX_PAGES={MAX_PAGES}"})
        return 1
    raw = sys.stdin.read() if args.text == "-" else args.text
    text = raw.rstrip()
    payload = {
        "page": args.page,
        "image_path": args.image,
        "text": text,
        "ts": dt.datetime.now().isoformat(timespec="seconds"),
    }
    out = session_dir / f"page-{args.page:03d}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _emit({"ok": True, "saved": str(out)})
    return 0


def cmd_merge_save(args: argparse.Namespace) -> int:
    """Merge all saved pages and write the final Obsidian Markdown."""
    session_dir = Path(args.session_dir)
    pages = _list_page_files(session_dir)
    if not pages:
        _emit({"ok": False, "error": f"no pages found in {session_dir}"})
        return 1

    texts = [json.loads(p.read_text(encoding="utf-8"))["text"] for p in pages]
    merged = texts[0]
    decisions: list[dict] = []
    uncertain_count = 0
    for nxt in texts[1:]:
        decision = best_overlap(merged, nxt)
        merged, meta = merge_pages(merged, nxt, decision)
        decisions.append(asdict(decision))
        if meta.merge_uncertain:
            uncertain_count += 1

    merged = merged.replace("---END---", "").rstrip() + "\n"

    now = dt.datetime.now()
    output = Path(args.output) if args.output else _default_output_path(args.vault, now)
    output.parent.mkdir(parents=True, exist_ok=True)

    frontmatter = _build_frontmatter(now, args.source, len(pages), uncertain_count)
    output.write_text(frontmatter + "\n" + merged, encoding="utf-8")
    _emit(
        {
            "ok": True,
            "output": str(output),
            "page_count": len(pages),
            "uncertain_boundaries": uncertain_count,
            "decisions": decisions,
        }
    )
    return 0


def _default_output_path(vault: str | None, now: dt.datetime) -> Path:
    base = Path(vault).expanduser() if vault else Path.cwd()
    return base / "00_Inbox" / f"clip-{now:%Y%m%d-%H%M}.md"


def _build_frontmatter(now: dt.datetime, source: str | None, pages: int, uncertain: int) -> str:
    refs = [source] if source else []
    lines = [
        "---",
        "tags:",
        "  - status/seed",
        "  - type/reference",
        "  - source/screen-read",
        f"created: {now:%Y-%m-%d %H:%M}",
        f"pages: {pages}",
        f"uncertain_boundaries: {uncertain}",
        "refs:",
    ]
    for r in refs:
        lines.append(f"  - {json.dumps(r, ensure_ascii=False)}")
    if not refs:
        lines.append("  - screen-read session")
    lines.append("---")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(prog="screen_read_helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pre = sub.add_parser("preprocess", help="blur check + EXIF strip + resize, in place")
    p_pre.add_argument("path")
    p_pre.add_argument("--force", action="store_true", help="continue even if blurry")
    p_pre.set_defaults(func=cmd_preprocess)

    p_same = sub.add_parser("same-page", help="pixel-diff sameness check between two images")
    p_same.add_argument("a")
    p_same.add_argument("b")
    p_same.add_argument("--threshold", type=float, default=2.0)
    p_same.set_defaults(func=cmd_same_page)

    p_save = sub.add_parser("save-page", help="record a page's OCR result")
    p_save.add_argument("--session-dir", required=True)
    p_save.add_argument("--page", type=int, required=True)
    p_save.add_argument("--image", required=True)
    p_save.add_argument("--text", default="-", help="OCR text or '-' to read from stdin")
    p_save.set_defaults(func=cmd_save_page)

    p_merge = sub.add_parser("merge-save", help="merge all saved pages and write Obsidian markdown")
    p_merge.add_argument("--session-dir", required=True)
    p_merge.add_argument("--output", help="explicit output path (otherwise uses --vault + 00_Inbox/clip-*.md)")
    p_merge.add_argument("--vault", help="Obsidian vault root for default output path")
    p_merge.add_argument("--source", help="source description for refs:")
    p_merge.set_defaults(func=cmd_merge_save)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
