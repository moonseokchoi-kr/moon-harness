"""hooks/lib/kompound_snapshot/wiki_log.py — F7/F10 index.md·log.md 갱신 (arch §6.3).

``wiki/index.md``와 ``wiki/log.md``에 대한 쓰기 형태 규율(arch §6.3):

- ``index.md``: Entries의 ``sdd-spec-registry`` 훅 문장 **그 한 줄만** 교체하고,
  최근 변경 섹션에는 새 항목을 **prepend**한다. Entries의 다른 줄과
  ``미해결 모순`` 섹션은 건드리지 않는다.
- ``log.md``: **append-only**로 배치 요약 1줄만 추가한다(AGENTS.md Bulk
  Ingest "배치 1건 = 로그 1줄").

F10 "동시 편집 충돌 — 양쪽 보존"은 이 쓰기 형태 자체로 성립한다: ``log.md``는
append-only, ``index.md`` 최근 변경은 prepend-only이고 기존 줄은 수정하지
않으므로, 사람의 동시 편집이 있어도 두 변경 모두 유실 없이 공존한다.

이 모듈은 **텍스트 변환만** 한다(부작용 없음, arch §3.2 ``wiki_log`` 행).
파일 IO·git 커밋은 호출자(T-10 ``apply.py``) 책임이다.

## 설계 결정 (arch에 없어 이 태스크가 직접 결정 — T-10이 참고할 것)

1. **본문 텍스트는 호출자가 조립한다.** arch §1 원칙 2("자동 편입은 강제,
   자동 판단은 금지... 주제 위키 합성·문장 작성은 하지 않는다")에 따라 이
   모듈은 Entries 훅 문장·최근 변경 항목의 **자연어 내용을 작성하지
   않는다** — 어디에 무엇을 스플라이스할지(구조)만 책임진다.
   ``update_index()``는 완성된 ``hook_line``/``recent_change_line`` 문자열을
   그대로 받아 지정된 위치에 놓는다. 다만 §6.3.0에 **리터럴로 확정된**
   log.md 배치 줄 형식만은 예외로, 이 모듈이 :func:`build_snapshot_log_line`
   으로 직접 조립한다(문장 작성이 아니라 arch가 이미 정한 템플릿의 기계적
   채움이기 때문).
2. **``append_log``는 정확히 한 줄만 추가한다.** 여러 줄을 한 번에 넣는
   인터페이스를 제공하지 않는다 — "배치 1건 = 로그 1줄" 규율을 API 표면
   에서부터 강제한다(호출자가 실수로 여러 줄을 append하는 경로 자체가
   없다).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = ["update_index", "append_log", "build_snapshot_log_line"]

_RECENT_CHANGES_HEADING = "## 최근 변경"
_HOOK_TARGET = "sdd-spec-registry"


def _find_hook_line(lines: Sequence[str]) -> Optional[int]:
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("-") and _HOOK_TARGET in stripped:
            return i
    return None


def _find_recent_changes_heading(lines: Sequence[str]) -> Optional[int]:
    for i, line in enumerate(lines):
        if line.strip() == _RECENT_CHANGES_HEADING:
            return i
    return None


def update_index(
    index_text: str,
    *,
    hook_line: str,
    recent_change_line: str,
) -> Dict[str, Any]:
    """``index.md``의 Entries 훅 문장 교체 + 최근 변경 prepend(arch §6.3).

    Args:
        index_text: 현재 ``wiki/index.md`` 전체 텍스트.
        hook_line: Entries의 ``sdd-spec-registry`` 훅 문장을 교체할 완성된
            한 줄(개행 없이). 이 모듈은 내용을 검사하지 않고 그대로 그
            줄을 치환한다.
        recent_change_line: 최근 변경 섹션 맨 위에 prepend할 완성된 한 줄.

    Returns:
        성공: ``{"ok": True, "text": str}``.
        실패(Entries 훅 문장 또는 ``## 최근 변경`` 헤딩을 찾지 못함):
        ``{"ok": False, "reason": "catalog_unparsed", "detail": str}``.
        예외를 던지지 않는다(F13 fail-safe).
    """
    try:
        return _update_index_impl(index_text, hook_line=hook_line, recent_change_line=recent_change_line)
    except Exception as exc:  # noqa: BLE001 — fail-safe
        return {"ok": False, "reason": "catalog_unparsed", "detail": f"unexpected error: {exc}"}


def _update_index_impl(index_text: str, *, hook_line: str, recent_change_line: str) -> Dict[str, Any]:
    lines: List[str] = index_text.splitlines()
    trailing_newline = index_text.endswith("\n")

    hook_idx = _find_hook_line(lines)
    if hook_idx is None:
        return {
            "ok": False,
            "reason": "catalog_unparsed",
            "detail": f"index.md Entries hook line for '{_HOOK_TARGET}' not found",
        }

    recent_idx = _find_recent_changes_heading(lines)
    if recent_idx is None:
        return {
            "ok": False,
            "reason": "catalog_unparsed",
            "detail": f"index.md '{_RECENT_CHANGES_HEADING}' heading not found",
        }

    new_lines = list(lines)
    new_lines[hook_idx] = hook_line

    insert_at = recent_idx + 1
    while insert_at < len(new_lines) and new_lines[insert_at].strip() == "":
        insert_at += 1
    new_lines.insert(insert_at, recent_change_line)

    text = "\n".join(new_lines) + ("\n" if trailing_newline else "")
    return {"ok": True, "text": text}


def append_log(log_text: str, *, line: str) -> Dict[str, Any]:
    """``log.md``에 정확히 한 줄을 append한다(AGENTS.md Bulk Ingest 규율).

    기존 내용은 전혀 수정하지 않는다(append-only) — F10 "양쪽 보존"의 근거.

    Args:
        log_text: 현재 ``wiki/log.md`` 전체 텍스트(빈 문자열 허용).
        line: 추가할 한 줄(개행 없이 전달해도, 있어도 무방 — 정확히 하나의
            개행으로 정규화해 붙인다).

    Returns:
        ``{"ok": True, "text": str}``. 이 함수는 실패 경로가 없다(순수 문자열
        접합) — 다만 패키지 전체 규약에 맞춰 예외는 던지지 않는다.
    """
    try:
        clean_line = line[:-1] if line.endswith("\n") else line
        if log_text == "":
            base = ""
        elif log_text.endswith("\n"):
            base = log_text
        else:
            base = log_text + "\n"
        text = base + clean_line + "\n"
        return {"ok": True, "text": text}
    except Exception as exc:  # noqa: BLE001 — fail-safe
        return {"ok": False, "reason": "catalog_unparsed", "detail": f"unexpected error: {exc}"}


def build_snapshot_log_line(
    date: str,
    total_raw: int,
    raw_commits: Sequence[Tuple[str, str]],
    catalog_commit: Tuple[str, str],
    retries: int,
) -> str:
    """§6.3.0 "raw/카탈로그 두 시점 표기" log.md 배치 줄을 조립한다(순수 함수).

    단일 raw 커밋: ``YYYY-MM-DD [snapshot] <N raw> — raw 커밋 <sha7>(날짜) ·
    카탈로그 <sha7>(날짜) · 재시도 K회``.
    다중 raw 커밋(카탈로그가 여러 번 실패한 뒤 성공 — "배치"의 정의가
    "카탈로그 성공 1회"로 넓어지는 경우, arch §6.3.0 N-2): ``<총 N raw>``
    표기로 바뀌고 raw 커밋들이 ``·``(공백 없음)로 전부 열거된다.

    Args:
        date: ``YYYY-MM-DD``.
        total_raw: 이 배치가 대표하는 raw 커밋들의 총 신규/갱신 문서 수.
        raw_commits: ``(sha7, date)`` 튜플의 시퀀스(발생 순서 그대로, 최소
            1개). 여러 개면 총계 표기가 ``<총 N raw>``로 바뀐다.
        catalog_commit: 카탈로그 커밋의 ``(sha7, date)``.
        retries: 카탈로그 재시도 횟수(0 이상).

    Returns:
        완성된 한 줄 문자열(개행 없음). 순수 함수 — 예외를 던지지 않는
        입력(빈 ``raw_commits``는 호출자 계약 위반이나, 방어적으로 총계
        표기만 ``<N raw>``로 두고 raw 커밋 목록은 빈 문자열이 된다).
    """
    is_multi = len(raw_commits) > 1
    total_marker = f"총 {total_raw}" if is_multi else f"{total_raw}"
    raw_part = "·".join(f"{sha}({d})" for sha, d in raw_commits)
    catalog_sha, catalog_date = catalog_commit
    return (
        f"{date} [snapshot] <{total_marker} raw> — raw 커밋 {raw_part} · "
        f"카탈로그 {catalog_sha}({catalog_date}) · 재시도 {retries}회"
    )
