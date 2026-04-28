"""Deterministic page-merge algorithm for OCR'ed Markdown pages.

Detects overlapping content between consecutive pages using RapidFuzz
near-string matching and merges them. The pseudocode reference is
``docs/結合アルゴリズム.md``.

Design invariants:
  - LLM produces OCR text only; merge decisions are made here.
  - Normalization is for similarity scoring **only**; the saved/output
    text is the original (NFKC etc. must not leak into Markdown bodies).
  - ``in_code`` mask is computed over the full page **before** slicing
    tail/head, so a slice that begins inside a fenced block does not
    flip the mask state.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz

TAIL_LINES = 40
HEAD_LINES = 60
MAX_SHIFT = 3
MIN_K = 1
MIN_SAFE_K = 3
MIN_SCORE = 91.0
PREFER_LONGER_WITHIN = 1.5
MAX_PAGES = 20

FENCE_RE = re.compile(r"^\s*```")
IGNORE_LINE_RE = re.compile(r"^\s*$|^[\W_]{1,}$|^\s*\d{1,3}\s*$")
HAS_ALNUM_RE = re.compile(r"[A-Za-z0-9぀-ヿ一-鿿]")


@dataclass
class OverlapDecision:
    ok: bool
    k: int
    score: float
    shift_prev: int
    shift_next: int
    reason: str


@dataclass
class MergeMeta:
    merge_uncertain: bool
    overlap: dict = field(default_factory=dict)


def split_lines(md: str) -> list[str]:
    return md.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def compute_in_code_mask(lines: list[str]) -> list[bool]:
    """Return one bool per line: is this line inside a fenced code block?

    Fence lines themselves carry the *pre-toggle* state (so the opening
    ``` is reported as outside-code, the closing ``` as inside-code),
    matching the original reference pseudocode.
    """
    in_code = False
    mask: list[bool] = []
    for line in lines:
        if FENCE_RE.match(line):
            mask.append(in_code)
            in_code = not in_code
            continue
        mask.append(in_code)
    return mask


def normalize_for_compare(line: str, in_code: bool) -> str:
    """Comparison-only normalization. Never apply to saved text."""
    line = line.replace("​", "")
    line = line.rstrip("\n")
    if in_code:
        line = line.replace("\t", "    ")
        return line.rstrip()
    s = unicodedata.normalize("NFKC", line)
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    s = s.replace("—", "-").replace("–", "-").replace("−", "-")
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def join_for_compare(lines: list[str], mask: list[bool]) -> str:
    return "\n".join(normalize_for_compare(ln, c) for ln, c in zip(lines, mask))


def is_ignorable(line: str) -> bool:
    return bool(IGNORE_LINE_RE.match(line))


def has_diversity(lines: list[str], min_alnum_lines: int = 2) -> bool:
    return sum(1 for ln in lines if HAS_ALNUM_RE.search(ln)) >= min_alnum_lines


def similarity(a: str, b: str) -> float:
    return float(fuzz.ratio(a, b))


def _max_ignorable_prefix(xs: list[str], limit: int) -> int:
    c = 0
    for i in range(min(len(xs), limit)):
        if is_ignorable(xs[i]):
            c += 1
        else:
            break
    return c


def best_overlap(
    prev_md: str,
    next_md: str,
    tail_lines: int = TAIL_LINES,
    head_lines: int = HEAD_LINES,
    max_shift: int = MAX_SHIFT,
    min_score: float = MIN_SCORE,
) -> OverlapDecision:
    prev_lines = split_lines(prev_md)
    next_lines = split_lines(next_md)

    prev_mask_full = compute_in_code_mask(prev_lines)
    next_mask_full = compute_in_code_mask(next_lines)

    tail_start = max(0, len(prev_lines) - tail_lines)
    tail = prev_lines[tail_start:]
    tail_mask = prev_mask_full[tail_start:]
    head = next_lines[:head_lines]
    head_mask = next_mask_full[:head_lines]

    ignorable_prefix = _max_ignorable_prefix(head, max_shift)
    best: Optional[OverlapDecision] = None

    for i in range(0, min(max_shift, len(tail)) + 1):
        for j in range(0, min(max_shift, len(head)) + 1):
            if j > ignorable_prefix:
                continue
            tail2 = tail[i:]
            head2 = head[j:]
            tail_mask2 = tail_mask[i:]
            head_mask2 = head_mask[j:]
            max_k = min(len(tail2), len(head2))
            if max_k < MIN_K:
                continue
            for k in range(max_k, MIN_K - 1, -1):
                a = join_for_compare(tail2[-k:], tail_mask2[-k:])
                b = join_for_compare(head2[:k], head_mask2[:k])
                sc = similarity(a, b)
                if sc < min_score:
                    continue

                if k < MIN_SAFE_K and not has_diversity(head2[:k]):
                    continue

                cand = OverlapDecision(
                    ok=True,
                    k=(j + k),
                    score=sc,
                    shift_prev=i,
                    shift_next=j,
                    reason=f"matched k={k} (drop next first {j}+{k} lines)",
                )
                if best is None:
                    best = cand
                elif (cand.score > best.score + PREFER_LONGER_WITHIN) or (
                    abs(cand.score - best.score) <= PREFER_LONGER_WITHIN
                    and cand.k > best.k
                ):
                    best = cand
                break

    if best is None:
        return OverlapDecision(
            ok=False,
            k=0,
            score=0.0,
            shift_prev=0,
            shift_next=0,
            reason="no overlap above threshold; boundary uncertain",
        )
    return best


def merge_pages(
    prev_md: str, next_md: str, decision: OverlapDecision
) -> tuple[str, MergeMeta]:
    """Merge two pages using the original (non-normalized) text.

    The normalized strings produced by ``normalize_for_compare`` are only
    used inside ``best_overlap`` for similarity scoring; they must never
    influence the saved Markdown.
    """
    prev_lines = split_lines(prev_md)
    next_lines = split_lines(next_md)
    if not decision.ok or decision.k <= 0:
        merged = (
            prev_md.rstrip()
            + "\n\n<!-- MERGE_UNCERTAIN: no reliable overlap -->\n\n"
            + next_md.lstrip()
        )
        return merged, MergeMeta(merge_uncertain=True, overlap=decision.__dict__)
    kept_next = next_lines[decision.k:]
    merged = "\n".join(prev_lines + kept_next)
    return merged, MergeMeta(merge_uncertain=False, overlap=decision.__dict__)
