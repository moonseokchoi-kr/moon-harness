"""tests/test_code_mapper_blockers.py — code-mapper "구현 걸림돌" 블록 정적 검사 (spec F3).

오프라인 전용. 기존 섹션 1~6·비목표·영속 금지 불변과 hooks/lib/code_mapper 무변경을 단언한다.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.lib.code_mapper import check_format_completeness  # noqa: E402

SKILL = REPO_ROOT / "skills" / "code-mapper" / "SKILL.md"

SECTION_HEADINGS = [
    "### 1. 진입점",
    "### 2. Callers (이 심볼을 호출하는 곳)",
    "### 3. Callees (이 심볼이 호출하는 것)",
    "### 4. 호출 경로 (Trace)",
    "### 5. Blast Radius (영향범위)",
    "### 6. 건드릴 파일 (이번 작업 추정)",
]


@pytest.fixture(scope="module")
def text() -> str:
    return SKILL.read_text(encoding="utf-8")


# --- F3 신규: 구현 걸림돌 블록 ---------------------------------------------

def test_blocker_block_named(text):
    assert "구현 걸림돌" in text


def test_blocker_block_is_conditional_on_requirements(text):
    assert "요구사항이 주어졌을 때만" in text


@pytest.mark.parametrize("item", ["영향받는 호출자", "불변식", "테스트", "제약"])
def test_blocker_block_lists_contents(text, item):
    idx = text.find("구현 걸림돌")
    assert idx != -1
    assert item in text[idx:]


def test_blocker_block_after_section_6(text):
    # 걸림돌 블록은 섹션 1~6 "뒤"에 붙는다.
    assert text.find("구현 걸림돌") > text.find("### 6. 건드릴 파일")


# --- 불변 회귀 --------------------------------------------------------------

def test_sections_1_to_6_order_and_labels_unchanged(text):
    positions = [text.find(h) for h in SECTION_HEADINGS]
    assert all(p != -1 for p in positions), positions
    assert positions == sorted(positions)


def test_search_method_label_kept(text):
    assert "탐색 방법: codegraph (MCP healthy) | grep 근사 (codegraph 미사용)" in text


def test_non_goals_section_and_no_persistence_kept(text):
    assert "## 비목표" in text
    assert "영속 금지" in text
    assert "ephemeral" in text


def test_template_block_still_passes_check_format_completeness(text):
    match = re.search(r"```markdown\n(## 코드맵:.*?)```", text, re.DOTALL)
    assert match, "F6 양식 코드블록이 없다"
    ok, missing = check_format_completeness(match.group(1))
    assert ok, missing


def test_core_package_unchanged_vs_head():
    proc = subprocess.run(
        ["git", "diff", "--stat", "HEAD", "--", "hooks/lib/code_mapper"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
