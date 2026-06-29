"""code-mapper — F6 커버리지 체크리스트 완전성/순서 검사 (순수 함수).

arch §8 / spec F6 기준. *주어진 마크다운 텍스트*가 F6 섹션 1~6 + "탐색 방법"
레이블을 모두, 올바른 순서로 포함하는지 검사한다. 동일 입력 = 동일 출력.

m3 책임 경계: 이 함수는 *보조 검증*이다. F6 포맷 불변량의 1차 방어는
SKILL.md 절차 + evals E2E이고, 여기서는 검사 함수 자체의 정확성만 보증한다.
"""

from __future__ import annotations

import re
from typing import List, Tuple

# F6 섹션 라벨 (순서가 곧 1~6). 헤딩 번호로 견고하게 매치한다.
# (text, regex) — regex가 섹션 헤딩 라인을 매치하면 존재로 간주.
_SECTIONS = (
    ("1. 진입점", re.compile(r"^#{1,6}\s*1\.\s*진입점", re.MULTILINE)),
    ("2. Callers", re.compile(r"^#{1,6}\s*2\.\s*Callers", re.MULTILINE)),
    ("3. Callees", re.compile(r"^#{1,6}\s*3\.\s*Callees", re.MULTILINE)),
    ("4. 호출 경로 (Trace)", re.compile(r"^#{1,6}\s*4\.\s*호출\s*경로", re.MULTILINE)),
    ("5. Blast Radius", re.compile(r"^#{1,6}\s*5\.\s*Blast\s*Radius", re.MULTILINE)),
    ("6. 건드릴 파일", re.compile(r"^#{1,6}\s*6\.\s*건드릴\s*파일", re.MULTILINE)),
)

# "탐색 방법" 레이블 (codegraph | grep 근사). 헤딩 아니어도 매치.
_PROBE_LABEL = re.compile(r"탐색\s*방법\s*[:：]")


def check_format_completeness(text: str) -> Tuple[bool, List[str]]:
    """F6 섹션 1~6 + "탐색 방법" 레이블의 존재와 순서를 검사한다.

    Args:
        text: F6 코드맵 마크다운 텍스트. 비문자열/빈 문자열 허용.

    Returns:
        ``(ok, missing)`` 튜플.
          - ``ok``      : 모든 섹션 + 레이블이 존재하고 순서가 올바르면 True.
          - ``missing`` : 누락된 항목 라벨 목록(+ 순서 오류는 ``"순서 오류: ..."``
                          항목으로 보고). ``ok``가 True면 빈 리스트.
    """
    if not isinstance(text, str):
        text = ""

    missing: List[str] = []
    positions: List[Tuple[str, int]] = []

    for label, pat in _SECTIONS:
        m = pat.search(text)
        if m is None:
            missing.append(label)
        else:
            positions.append((label, m.start()))

    if _PROBE_LABEL.search(text) is None:
        missing.append("탐색 방법")

    # 순서 검사: 발견된 섹션들의 등장 위치가 1→6 단조 증가여야 한다.
    for i in range(1, len(positions)):
        if positions[i][1] < positions[i - 1][1]:
            missing.append(
                f"순서 오류: {positions[i][0]}가 {positions[i - 1][0]}보다 먼저 나옴"
            )

    ok = len(missing) == 0
    return ok, missing
