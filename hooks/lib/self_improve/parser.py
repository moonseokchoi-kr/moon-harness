"""LEARNING.md entry + provenance/tag parser.

Parses the LEARNING.md ledger into structured entries. Each entry starts at a
``##`` markdown header and may carry a tag metablock immediately after the
header (spec 해결 1 / arch §6, load-bearing contract):

    ## {YYYY-MM-DD} — {feature-slug} / {task-id}
    <!-- tags: domain={영역}, stage={구현|pr-converge}, provenance_repo={repo-id} -->

Entries without a tag metablock parse successfully with ``tags=None`` — the
parser never raises on a missing or malformed metablock (fail-safe, F20).

Pure, deterministic, stdlib-only (the ``re`` module is explicitly allowed).
No LLM/gh/network calls.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# An entry header: a line beginning with "## " (exactly H2, not H1/H3).
_HEADER_RE = re.compile(r"^##(?!#)\s*(.*)$")

# The tag metablock as a whole: "<!-- tags: ... -->" on a single line.
_TAGS_BLOCK_RE = re.compile(r"<!--\s*tags:\s*(?P<body>.*?)\s*-->")

# Individual "key=value" pairs inside the metablock body, comma-separated.
# Values may contain spaces and any char except a comma (which separates pairs).
_TAG_PAIR_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>[^,]*)")


def _parse_tags(block_body: str) -> Dict[str, str]:
    """Parse the inner body of a tags metablock into a key->value dict.

    Empty values are preserved as empty strings. Unknown keys are kept so the
    contract can extend without losing data.
    """
    tags: Dict[str, str] = {}
    for m in _TAG_PAIR_RE.finditer(block_body):
        key = m.group("key").strip()
        val = m.group("val").strip()
        if key:
            tags[key] = val
    return tags


def parse_learning_entry(text: str) -> List[Dict[str, object]]:
    """Parse LEARNING.md text into a list of entry dicts.

    Each entry dict has the shape::

        {
            "marker": str,      # the H2 header line content (without "## ")
            "body": str,        # the entry body text (tags line excluded)
            "tags": dict | None,# parsed tag key/values, or None if absent
            "raw": str,         # the full raw entry text including the header
        }

    Content before the first ``##`` header (a preamble / title) is ignored.
    A missing or malformed tag metablock yields ``tags=None`` without raising.
    """
    if not isinstance(text, str) or not text.strip():
        return []

    lines = text.splitlines()
    entries: List[Dict[str, object]] = []

    # Collect (header_index, marker) for each H2 header.
    header_positions: List[int] = []
    for idx, line in enumerate(lines):
        if _HEADER_RE.match(line):
            header_positions.append(idx)

    if not header_positions:
        return []

    for i, start in enumerate(header_positions):
        end = header_positions[i + 1] if i + 1 < len(header_positions) else len(lines)
        block_lines = lines[start:end]

        header_match = _HEADER_RE.match(block_lines[0])
        marker = header_match.group(1).strip() if header_match else ""

        raw = "\n".join(block_lines)

        # Locate a tags metablock anywhere within the entry (typically the
        # line immediately after the header).
        tags: Optional[Dict[str, str]] = None
        body_lines: List[str] = []
        for bl in block_lines[1:]:
            tag_match = _TAGS_BLOCK_RE.search(bl)
            if tag_match and tags is None:
                tags = _parse_tags(tag_match.group("body"))
                # the tags line is metadata, excluded from body
                continue
            body_lines.append(bl)

        body = "\n".join(body_lines).strip()

        entries.append(
            {
                "marker": marker,
                "body": body,
                "tags": tags,
                "raw": raw,
            }
        )

    return entries


def extract_provenance(entry: Dict[str, object]) -> Dict[str, Optional[str]]:
    """Extract provenance fields from a parsed entry.

    Returns a dict with keys ``provenance_repo``, ``stage``, ``domain``. Any
    field absent from the entry's tags (or an untagged entry) yields ``None``
    for that key. Fail-safe: a malformed entry never raises.
    """
    result: Dict[str, Optional[str]] = {
        "provenance_repo": None,
        "stage": None,
        "domain": None,
    }
    if not isinstance(entry, dict):
        return result

    tags = entry.get("tags")
    if not isinstance(tags, dict):
        return result

    for key in result:
        val = tags.get(key)
        if isinstance(val, str) and val != "":
            result[key] = val
    return result
