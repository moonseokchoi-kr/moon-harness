"""Pre-check engine for improvement candidates (spec F10).

``run_prechecks(candidate, target_file_text)``

    Sequentially applies three deterministic checks to an improvement
    candidate before any LLM / critic-agent call:

    1. **Conflict check** (``conflict``): does the target file already contain
       a rule/statement that directly contradicts the candidate's intent?
    2. **Duplicate check** (``duplicate``): does the target file already
       contain the same or equivalent content?
    3. **Sparsity check** (``too_sparse``): is the evidence base too thin to
       justify a behaviour-rule change?

    Each check sets a boolean flag and a human-readable ``reason`` string in
    the returned dict.  The function never raises (fail-safe) and never calls
    LLM or network APIs (F20).

Return shape::

    {
        "conflict":   bool,
        "conflict_reason":   str,
        "duplicate":  bool,
        "duplicate_reason":  str,
        "too_sparse": bool,
        "too_sparse_reason": str,
        "passed":     bool,   # True iff all three checks are clear
    }

Design notes
------------
- All text comparisons are **case-insensitive** to reduce false negatives from
  capitalisation differences.
- Keyword extraction keeps the top-N significant tokens from ``candidate``'s
  ``body`` and ``marker`` after stripping stop-words and punctuation.
- The conflict heuristic looks for negation phrases ("금지", "하지 말라",
  "do not", "never", "must not") co-occurring with candidate keywords in the
  target file — a simple but LLM-free signal.
- Sparsity is determined via ``count_signals`` from ``recurrence.py``:
  independent signals < 2 AND no repetition signal in the body → too_sparse.
"""

from __future__ import annotations

import re
import string
from typing import Any, Dict, List, Optional, Set

from hooks.lib.self_improve.recurrence import count_signals

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Common Korean + English stop-words to skip when building keyword sets.
_STOP_WORDS: Set[str] = {
    # Korean
    "이", "가", "을", "를", "은", "는", "에", "에서", "의", "로", "으로",
    "과", "와", "도", "만", "뿐", "까지", "부터", "나", "이나", "또는",
    "및", "그", "그리고", "하지만", "그러나", "때", "것", "수", "있다",
    "없다", "한다", "하다", "됩니다", "합니다", "했다", "했습니다",
    # English
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "this", "that", "it", "its", "if", "when", "then", "not", "no",
}

# Negation / prohibition phrases that may signal a conflict.
_NEGATION_RE = re.compile(
    r"(금지|하지\s*말|do\s+not|don'?t|never|must\s+not|should\s+not|"
    r"prohibited|forbidden|avoid|절대)",
    re.IGNORECASE,
)

# Repetition-signal phrases in the candidate body (spec F10 / F9).
# Uses word boundaries (\b) for English terms to avoid false matches inside
# longer words (e.g. "recurrence" should not trigger on "recur").
_REPETITION_RE = re.compile(
    r"(또\s*그러네|반복|재발|동일\s+패턴|같은\s+오류|계속"
    r"|\brecurring\b|\brecurred\b|\brecurs\b"
    r"|\bagain\b|\brepeatedly\b|\brepeated\b|\brepeats\b"
    r"|\bmultiple\s+times\b|\bsame\s+issue\b)",
    re.IGNORECASE,
)

# Minimum number of independent signals required to avoid sparsity demotion.
_MIN_SIGNALS = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> Set[str]:
    """Return a lower-cased set of significant tokens from ``text``.

    Strips punctuation, splits on whitespace, and removes stop-words and
    single-character tokens.
    """
    if not isinstance(text, str):
        return set()
    # Remove markdown formatting and HTML-like tags.
    cleaned = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    cleaned = re.sub(r"[`*#_~>]", " ", cleaned)
    # Split on whitespace and strip punctuation from each token.
    tokens: Set[str] = set()
    for tok in cleaned.split():
        tok = tok.strip(string.punctuation).lower()
        if tok and tok not in _STOP_WORDS and len(tok) > 1:
            tokens.add(tok)
    return tokens


def _candidate_keywords(candidate: Dict[str, Any]) -> Set[str]:
    """Extract significant keywords from a candidate dict."""
    parts: List[str] = []
    if isinstance(candidate.get("marker"), str):
        parts.append(candidate["marker"])
    if isinstance(candidate.get("body"), str):
        parts.append(candidate["body"])
    return _tokenise(" ".join(parts))


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_conflict(
    keywords: Set[str],
    target_text: str,
) -> tuple[bool, str]:
    """Conflict check: does target contain a contradicting negation near our keywords?

    Heuristic: look for negation phrases within a sliding window of ±3 lines
    that also share at least one candidate keyword with the target line context.
    This avoids an expensive full-text parse while still catching obvious
    contradictions (e.g., "절대 하지 말라" near the same topic tokens).
    """
    if not keywords or not isinstance(target_text, str):
        return False, ""

    target_lower = target_text.lower()
    lines = target_lower.splitlines()
    window = 3

    for i, line in enumerate(lines):
        line_tokens = _tokenise(line)
        if not line_tokens.intersection(keywords):
            continue  # this line doesn't mention our topic

        # Check a ±window neighbourhood for negation phrases.
        lo = max(0, i - window)
        hi = min(len(lines), i + window + 1)
        neighbourhood = " ".join(lines[lo:hi])
        if _NEGATION_RE.search(neighbourhood):
            return True, (
                f"Target file contains a negation/prohibition near keyword(s) "
                f"{sorted(line_tokens.intersection(keywords))[:3]} "
                f"(lines {lo + 1}–{hi})."
            )

    return False, ""


def _check_duplicate(
    keywords: Set[str],
    target_text: str,
) -> tuple[bool, str]:
    """Duplicate check: is the candidate's substance already in target_file_text?

    The check is positive when the majority (>= 60 %) of candidate keywords
    appear in the target file.  This tolerates minor wording differences while
    still catching semantically equivalent content.
    """
    if not keywords or not isinstance(target_text, str):
        return False, ""

    target_tokens = _tokenise(target_text)
    overlap = keywords.intersection(target_tokens)

    if not keywords:
        return False, ""

    ratio = len(overlap) / len(keywords)
    if ratio >= 0.60:
        return True, (
            f"Candidate keywords overlap with target file by "
            f"{len(overlap)}/{len(keywords)} ({ratio:.0%}): "
            f"{sorted(overlap)[:5]}."
        )

    return False, ""


def _check_too_sparse(
    candidate: Dict[str, Any],
    entries: List[Dict[str, Any]],
) -> tuple[bool, str]:
    """Sparsity check: is the evidence base sufficient?

    Conditions for ``too_sparse=True`` (spec F10):
    - Independent signal count < 2 (``same_repo`` from count_signals), AND
    - No repetition phrase found in the candidate body.

    Rationale: a single occurrence without any explicit "recurring" language
    in the entry is too weak to justify a behaviour-rule change.
    """
    body = candidate.get("body", "") if isinstance(candidate.get("body"), str) else ""

    has_repetition_signal = bool(_REPETITION_RE.search(body))
    if has_repetition_signal:
        return False, ""

    # count_signals aggregates the full entries list to get the per-cluster count.
    counter = count_signals(entries)

    # Determine the cluster key for this candidate (same logic as recurrence).
    from hooks.lib.self_improve.recurrence import _cluster_key_for
    key = _cluster_key_for(candidate)

    cluster = counter.get(key, {})
    signal_count: int = cluster.get("same_repo", 0)

    if signal_count < _MIN_SIGNALS:
        return True, (
            f"Only {signal_count} independent signal(s) for cluster '{key}' "
            f"(need >= {_MIN_SIGNALS}) and no repetition phrase in body."
        )

    return False, ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_prechecks(
    candidate: Dict[str, Any],
    target_file_text: str,
    entries: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run the three pre-checks on ``candidate`` against ``target_file_text``.

    Args:
        candidate: a parsed entry dict (``marker``, ``body``, ``tags``, ``raw``).
        target_file_text: the current full text of the improvement target file.
        entries: the full list of new entries being evaluated in this run
            (used for sparsity counting).  Defaults to ``[candidate]`` when
            omitted.

    Returns:
        A dict with keys::

            conflict, conflict_reason,
            duplicate, duplicate_reason,
            too_sparse, too_sparse_reason,
            passed   (True iff all three are clear)
    """
    # Fail-safe defaults.
    result: Dict[str, Any] = {
        "conflict": False,
        "conflict_reason": "",
        "duplicate": False,
        "duplicate_reason": "",
        "too_sparse": False,
        "too_sparse_reason": "",
        "passed": True,
    }

    if not isinstance(candidate, dict):
        result["too_sparse"] = True
        result["too_sparse_reason"] = "Candidate is not a dict."
        result["passed"] = False
        return result

    if entries is None:
        entries = [candidate]

    keywords = _candidate_keywords(candidate)
    target_text = target_file_text if isinstance(target_file_text, str) else ""

    # 1. Conflict check.
    conflict, conflict_reason = _check_conflict(keywords, target_text)
    result["conflict"] = conflict
    result["conflict_reason"] = conflict_reason

    # 2. Duplicate check.
    duplicate, duplicate_reason = _check_duplicate(keywords, target_text)
    result["duplicate"] = duplicate
    result["duplicate_reason"] = duplicate_reason

    # 3. Sparsity check.
    too_sparse, too_sparse_reason = _check_too_sparse(candidate, entries)
    result["too_sparse"] = too_sparse
    result["too_sparse_reason"] = too_sparse_reason

    result["passed"] = not (conflict or duplicate or too_sparse)
    return result
