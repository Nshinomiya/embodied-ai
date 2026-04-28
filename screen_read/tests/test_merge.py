from __future__ import annotations

from merge import (
    MIN_SAFE_K,
    best_overlap,
    compute_in_code_mask,
    has_diversity,
    is_ignorable,
    merge_pages,
    normalize_for_compare,
    split_lines,
)


def test_split_lines_handles_crlf_and_cr():
    assert split_lines("a\nb\r\nc\rd") == ["a", "b", "c", "d"]


def test_compute_in_code_mask_full_page():
    lines = [
        "intro",          # outside
        "```python",      # fence open: pre-toggle = outside
        "code1",          # inside
        "code2",          # inside
        "```",            # fence close: pre-toggle = inside
        "outro",          # outside
    ]
    assert compute_in_code_mask(lines) == [False, False, True, True, True, False]


def test_compute_in_code_mask_slice_does_not_lose_state():
    """Slicing the full page must not reset the in_code flag.

    If we sliced first and then computed the mask, code lines whose fence
    was on a previous line would be misclassified as outside-code.
    """
    full = ["```", "code", "code", "```", "tail1", "tail2"]
    full_mask = compute_in_code_mask(full)
    sliced_mask = full_mask[2:4]
    assert sliced_mask == [True, True]


def test_normalize_for_compare_collapses_text_whitespace():
    assert normalize_for_compare("  foo   bar  ", in_code=False) == "foo bar"


def test_normalize_for_compare_preserves_code_indent():
    line = "\t    if x:"
    out = normalize_for_compare(line, in_code=True)
    assert out.startswith("        ")
    assert out.endswith("if x:")


def test_normalize_for_compare_unifies_quotes_and_dashes():
    assert normalize_for_compare("“hi” — ok", in_code=False) == '"hi" - ok'


def test_is_ignorable():
    assert is_ignorable("")
    assert is_ignorable("   ")
    assert is_ignorable("---")
    assert is_ignorable("  42  ")
    assert not is_ignorable("hello")


def test_has_diversity():
    assert has_diversity(["abc", "def"])
    assert not has_diversity(["abc"])
    assert not has_diversity(["", " "])


def test_best_overlap_finds_clean_match():
    prev = "\n".join(
        [
            "header",
            "line A",
            "line B with content",
            "line C describing things",
            "line D extra context",
        ]
    )
    next_ = "\n".join(
        [
            "line B with content",
            "line C describing things",
            "line D extra context",
            "line E new content",
            "line F more new",
        ]
    )
    decision = best_overlap(prev, next_)
    assert decision.ok
    assert decision.score >= 91.0
    assert decision.k >= MIN_SAFE_K


def test_best_overlap_no_overlap():
    prev = "\n".join(["the quick brown fox", "jumps over the lazy dog"])
    next_ = "\n".join(["totally different paragraph", "with unrelated content here"])
    decision = best_overlap(prev, next_)
    assert not decision.ok


def test_best_overlap_skips_short_low_diversity_match():
    """Two pages whose only "overlap" is a single empty/symbol line
    must not be merged on that basis."""
    prev = "\n".join(["unique top content alpha", "unique top content beta", "---"])
    next_ = "\n".join(["---", "completely different gamma", "completely different delta"])
    decision = best_overlap(prev, next_)
    assert not decision.ok


def test_merge_pages_drops_overlap_in_next():
    prev = "\n".join(
        [
            "alpha alpha",
            "beta beta line",
            "gamma gamma line",
            "delta delta line",
        ]
    )
    next_ = "\n".join(
        [
            "beta beta line",
            "gamma gamma line",
            "delta delta line",
            "epsilon new content",
            "zeta new line",
        ]
    )
    decision = best_overlap(prev, next_)
    merged, meta = merge_pages(prev, next_, decision)
    assert not meta.merge_uncertain
    assert merged.count("delta delta line") == 1
    assert "epsilon new content" in merged
    assert "alpha alpha" in merged


def test_merge_pages_marks_uncertain_when_no_overlap():
    prev = "alpha\nbeta"
    next_ = "totally unrelated\ncontent here"
    decision = best_overlap(prev, next_)
    merged, meta = merge_pages(prev, next_, decision)
    assert meta.merge_uncertain
    assert "MERGE_UNCERTAIN" in merged
    assert "alpha" in merged and "totally unrelated" in merged


def test_merge_pages_preserves_original_text_unchanged():
    """NFKC and other comparison-only normalizations must not leak into
    the saved Markdown body."""
    prev = "\n".join(["“quoted text”", "shared line one alpha", "shared line two beta"])
    next_ = "\n".join(
        ["shared line one alpha", "shared line two beta", "新しい段落 — em-dash"]
    )
    decision = best_overlap(prev, next_)
    merged, meta = merge_pages(prev, next_, decision)
    assert not meta.merge_uncertain
    assert "“quoted text”" in merged
    assert "—" in merged
