"""tests/test_tag_parser.py — parse_learning_entry / extract_provenance 단위 테스트.

오프라인 전용. golden fixture(tests/fixtures/sample_learning.md) 사용.
태그 없는 엔트리도 파싱 실패 없이 처리됨(tags=None)을 검증.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.lib.self_improve import (  # noqa: E402
    extract_provenance,
    parse_learning_entry,
)

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_learning.md"


@pytest.fixture()
def entries():
    text = FIXTURE.read_text(encoding="utf-8")
    return parse_learning_entry(text)


def test_entry_count(entries):
    # fixture has 4 entries (preamble before first ## must be ignored)
    assert len(entries) == 4


def test_entry_shape(entries):
    for e in entries:
        assert set(e.keys()) == {"marker", "body", "tags", "raw"}
        assert isinstance(e["marker"], str)
        assert isinstance(e["body"], str)
        assert isinstance(e["raw"], str)


def test_first_entry_tags(entries):
    e = entries[0]
    assert e["marker"] == "2026-06-10 — auth-refresh / T-12"
    assert e["tags"] == {
        "domain": "auth",
        "stage": "구현",
        "provenance_repo": "moon-harness",
    }
    # tags line excluded from body
    assert "<!-- tags:" not in e["body"]
    assert "Refresh tokens" in e["body"]
    # raw retains the header
    assert e["raw"].startswith("## 2026-06-10")


def test_second_entry_tags(entries):
    e = entries[1]
    prov = extract_provenance(e)
    assert prov == {
        "provenance_repo": "marvelous",
        "stage": "pr-converge",
        "domain": "pr-converge",
    }


def test_untagged_entry_parses_without_failure(entries):
    e = entries[2]
    assert e["marker"] == "2026-06-12 — quick-note / T-3"
    assert e["tags"] is None
    assert "NO tag metablock" in e["body"]


def test_extract_provenance_on_untagged_entry(entries):
    prov = extract_provenance(entries[2])
    assert prov == {
        "provenance_repo": None,
        "stage": None,
        "domain": None,
    }


def test_multiline_entry_body(entries):
    e = entries[3]
    assert e["marker"] == "2026-06-13 — multiline-pipeline / T-9"
    assert e["tags"]["domain"] == "pipeline"
    # body preserves multiple lines / bullets
    assert "bullet one" in e["body"]
    assert "bullet two" in e["body"]
    assert "Final line of the multiline entry." in e["body"]
    assert e["body"].count("\n") >= 3


# --- Edge / fail-safe cases ----------------------------------------------

def test_empty_text_returns_empty_list():
    assert parse_learning_entry("") == []
    assert parse_learning_entry("   \n\n") == []


def test_non_string_returns_empty_list():
    assert parse_learning_entry(None) == []  # type: ignore[arg-type]


def test_text_with_no_headers_returns_empty():
    assert parse_learning_entry("just some prose\nwith no headers") == []


def test_h1_and_h3_not_treated_as_entry_headers():
    text = "# Title\n### Sub\nbody\n## Real Entry\ncontent"
    parsed = parse_learning_entry(text)
    assert len(parsed) == 1
    assert parsed[0]["marker"] == "Real Entry"


def test_malformed_tag_block_does_not_raise():
    text = "## E1\n<!-- tags: domain= , stage= -->\nbody"
    parsed = parse_learning_entry(text)
    assert len(parsed) == 1
    # empty values preserved as empty strings; extract -> None for empties
    prov = extract_provenance(parsed[0])
    assert prov["domain"] is None
    assert prov["stage"] is None
    assert prov["provenance_repo"] is None


def test_extract_provenance_non_dict_input():
    out = extract_provenance("not a dict")  # type: ignore[arg-type]
    assert out == {"provenance_repo": None, "stage": None, "domain": None}
