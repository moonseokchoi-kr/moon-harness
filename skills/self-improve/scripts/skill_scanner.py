"""skill_scanner.py — F19 minor①: glob SKILL.md files + description dedup.

Scans ``skills/**/SKILL.md`` under a given root directory, extracts the
``description`` field from YAML frontmatter, and detects simple text-overlap
duplicates between skills.

No LLM calls.  Duplicate detection is intentionally simple (token overlap
≥ 0.5 of the shorter description) — the result is a suggestion list, not an
auto-merge.  The final dedup/merge decision always goes to the human or to
write_harness_proposal() (F19 Acceptance: "dedup/merge를 제안").

Pure stdlib, no network, no LLM calls (F20). Never raises.
"""

from __future__ import annotations

import re
import string
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ── Frontmatter extraction ────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*(?:\n|$)",
    re.DOTALL,
)
_DESCRIPTION_RE = re.compile(
    r'^description\s*:\s*["\']?(.*?)["\']?\s*$',
    re.MULTILINE | re.IGNORECASE,
)


def _extract_description(skill_md_text: str) -> Optional[str]:
    """Extract the ``description`` value from YAML frontmatter.

    Returns None if no frontmatter or no description field is found.
    """
    fm_match = _FRONTMATTER_RE.match(skill_md_text)
    if not fm_match:
        return None
    frontmatter = fm_match.group(1)
    desc_match = _DESCRIPTION_RE.search(frontmatter)
    if not desc_match:
        return None
    desc = desc_match.group(1).strip().strip('"').strip("'")
    return desc if desc else None


# ── Token helpers ─────────────────────────────────────────────────────────────

_STOP_WORDS: Set[str] = {
    "a", "an", "the", "and", "or", "for", "in", "on", "at", "to",
    "of", "with", "by", "is", "are", "be", "this", "that", "it",
    "이", "가", "을", "를", "은", "는", "에", "의", "로", "과", "와",
    "및", "한", "하는", "하여", "합니다", "된다", "이다",
}


def _tokenise(text: str) -> Set[str]:
    """Lower-case significant token set for overlap comparison."""
    if not isinstance(text, str):
        return set()
    cleaned = re.sub(r"[`*#_~>]", " ", text)
    tokens: Set[str] = set()
    for tok in cleaned.split():
        tok = tok.strip(string.punctuation).lower()
        if tok and tok not in _STOP_WORDS and len(tok) > 1:
            tokens.add(tok)
    return tokens


def _overlap_ratio(a: str, b: str) -> float:
    """Return overlap / min(len_a, len_b) for the token sets of a and b."""
    tokens_a = _tokenise(a)
    tokens_b = _tokenise(b)
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    denom = min(len(tokens_a), len(tokens_b))
    return overlap / denom if denom else 0.0


# ── Scanner ───────────────────────────────────────────────────────────────────

def scan_skills(
    root: str | Path,
    duplicate_threshold: float = 0.5,
) -> Dict[str, Any]:
    """Glob ``skills/**/SKILL.md`` under root and detect description duplicates.

    Args:
        root: repository root directory (the directory that contains
            ``skills/``).
        duplicate_threshold: token-overlap ratio ≥ this value → flag as
            potential duplicate. Default 0.5 (50%).

    Returns:
        A dict::

            {
                "skills": [
                    {
                        "path":        str,   # relative POSIX path
                        "description": str|None,
                    },
                    ...
                ],
                "duplicate_pairs": [
                    {
                        "a": str,   # path of skill A
                        "b": str,   # path of skill B
                        "overlap_ratio": float,
                    },
                    ...
                ],
                "skill_count":     int,
                "duplicate_count": int,
            }

        A duplicate_pair is a suggestion only — no files are modified.

    Fail-safe: unreadable files are skipped silently (a warning entry with
    ``description=None`` is included so the caller can surface them).
    """
    root_path = Path(root) if not isinstance(root, Path) else root

    skills_dir = root_path / "skills"
    skill_files = sorted(skills_dir.glob("**/SKILL.md")) if skills_dir.is_dir() else []

    skill_records: List[Dict[str, Any]] = []
    for sf in skill_files:
        rel = sf.relative_to(root_path).as_posix()
        try:
            text = sf.read_text(encoding="utf-8")
            desc = _extract_description(text)
        except Exception:  # noqa: BLE001
            desc = None
        skill_records.append({"path": rel, "description": desc})

    # Detect duplicate pairs (O(n²) — skill count is small).
    duplicate_pairs: List[Dict[str, Any]] = []
    for i in range(len(skill_records)):
        for j in range(i + 1, len(skill_records)):
            desc_a = skill_records[i]["description"]
            desc_b = skill_records[j]["description"]
            if not desc_a or not desc_b:
                continue
            ratio = _overlap_ratio(desc_a, desc_b)
            if ratio >= duplicate_threshold:
                duplicate_pairs.append(
                    {
                        "a": skill_records[i]["path"],
                        "b": skill_records[j]["path"],
                        "overlap_ratio": round(ratio, 3),
                    }
                )

    return {
        "skills": skill_records,
        "duplicate_pairs": duplicate_pairs,
        "skill_count": len(skill_records),
        "duplicate_count": len(duplicate_pairs),
    }
