"""hooks/lib/kompound_snapshot/wiki_log.py — F7/F10 index.md·log.md 갱신 (arch §6.3).

v2 볼트(2026-10-07~) 루트 ``index.md``와 ``log.md``에 대한 쓰기 형태 규율:

- ``index.md``: ``- [[SDD Spec Registry]] — ...`` 훅 문장 **그 한 줄만** 교체하고,
  ``## 📥 Recent Ingests`` 섹션의 첫 목록 항목 앞에 새 항목을 **prepend**한다
  (``- YYYY-MM-DD [snapshot] ...``, 최신순). 다른 줄과 ``## ⚠️ Open
  Contradictions`` 섹션은 건드리지 않는다.
- ``log.md``: **append-only**로 배치 1건 = 엔트리 1개만 추가한다
  (``## [YYYY-MM-DD] snapshot | <제목>`` + 빈 줄 + ``- <요약>``).

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

__all__ = ["update_index", "append_log", "build_snapshot_log_line", "build_log_entry"]

_RECENT_CHANGES_TITLE = "Recent Ingests"  # `## 📥 Recent Ingests` (이모지 유무 무관)
_HOOK_TARGET = "SDD Spec Registry"
_HOOK_LINK_ANCHOR = f"- [[{_HOOK_TARGET}]]"


def _find_hook_line(lines: Sequence[str]) -> Optional[int]:
    """``- [[SDD Spec Registry]]`` 로 **시작하는** 목록 줄 하나를 찾는다.

    줄 시작 앵커 매칭이라, 다른 항목이 설명 문장 안에서 ``[[SDD Spec Registry]]``
    를 언급하는 줄은 대상이 아니다(v1 리뷰 [P1] 함정과 같은 원칙 — 사람이 쓴
    설명 줄을 덮어쓰지 않는다). ``[[SDD Spec Registry|별칭]]`` 형태도 허용한다.
    """
    alias_anchor = f"- [[{_HOOK_TARGET}|"
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(_HOOK_LINK_ANCHOR) or stripped.startswith(alias_anchor):
            return i
    return None


def _find_recent_changes_heading(lines: Sequence[str]) -> Optional[int]:
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## ") and stripped.endswith(_RECENT_CHANGES_TITLE):
            return i
    return None


def _recent_insert_position(lines: Sequence[str], heading_idx: int) -> int:
    """Recent Ingests 섹션의 첫 목록 항목 위치(최신순 prepend). 항목이 없으면
    섹션 머리말(빈 줄·인용문) 뒤."""
    end = len(lines)
    for i in range(heading_idx + 1, len(lines)):
        if lines[i].startswith("## ") or lines[i].strip() == "---":
            end = i
            break
    for i in range(heading_idx + 1, end):
        if lines[i].lstrip().startswith("- "):
            return i
    pos = heading_idx + 1
    while pos < end and (lines[pos].strip() == "" or lines[pos].lstrip().startswith(">")):
        pos += 1
    return pos


def update_index(
    index_text: str,
    *,
    hook_line: str,
    recent_change_line: str,
) -> Dict[str, Any]:
    """``index.md``의 Entries 훅 문장 교체 + 최근 변경 prepend(arch §6.3).

    Args:
        index_text: 현재 볼트 루트 ``index.md`` 전체 텍스트.
        hook_line: ``- [[SDD Spec Registry]] — ...`` 훅 문장을 교체할 완성된
            한 줄(개행 없이). 교체 대상은 ``- [[SDD Spec Registry]]``로 시작하는
            줄 하나다.
        recent_change_line: ``## 📥 Recent Ingests`` 첫 항목 앞에 prepend할
            완성된 한 줄.

    Returns:
        성공: ``{"ok": True, "text": str}``.
        실패(훅 줄 또는 ``Recent Ingests`` 헤딩을 찾지 못함):
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
            "detail": f"index.md hook line '{_HOOK_LINK_ANCHOR}' not found",
        }

    recent_idx = _find_recent_changes_heading(lines)
    if recent_idx is None:
        return {
            "ok": False,
            "reason": "catalog_unparsed",
            "detail": f"index.md '## ... {_RECENT_CHANGES_TITLE}' heading not found",
        }

    new_lines = list(lines)
    new_lines[hook_idx] = hook_line

    insert_at = _recent_insert_position(new_lines, recent_idx)
    new_lines.insert(insert_at, recent_change_line)

    text = "\n".join(new_lines) + ("\n" if trailing_newline else "")
    return {"ok": True, "text": text}


def build_log_entry(date: str, op: str, title: str, summary: str) -> str:
    """v2 ``log.md`` 엔트리 블록(순수 함수, 끝 개행 없음)::

        ## [YYYY-MM-DD] <op> | <title>

        - <summary>
    """
    return f"## [{date}] {op} | {title}\n\n- {summary}"


def append_log(log_text: str, *, line: str) -> Dict[str, Any]:
    """``log.md`` 끝에 엔트리 **하나**를 append한다(배치 1건 = 엔트리 1개).

    ``line``은 :func:`build_log_entry`가 만든 블록(여러 줄)이거나 한 줄 문자열이다.
    기존 내용은 전혀 수정하지 않는다(append-only) — F10 "양쪽 보존"의 근거.
    기존 텍스트와 새 엔트리 사이에는 빈 줄 하나를 둔다(v2 log.md 형식 —
    엔트리가 ``##`` 헤딩이므로 구분이 필요하다).

    Returns:
        ``{"ok": True, "text": str}``. 예외는 던지지 않는다.
    """
    try:
        entry = line.rstrip("\n")
        if log_text.strip() == "":
            base = ""
        else:
            base = log_text.rstrip("\n") + "\n\n"
        text = base + entry + "\n"
        return {"ok": True, "text": text}
    except Exception as exc:  # noqa: BLE001 — fail-safe
        return {"ok": False, "reason": "catalog_unparsed", "detail": f"unexpected error: {exc}"}


def build_snapshot_log_line(
    date: str,
    total_raw: int,
    raw_commits: Sequence[Tuple[str, str]],
    catalog_commit: Tuple[str, str],
    retries: int,
    *,
    with_prefix: bool = True,
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
        with_prefix: False면 ``YYYY-MM-DD [snapshot] `` 접두 없이 요약만 낸다
            (v2 log.md 엔트리의 ``- <요약>`` 줄용).

    Returns:
        완성된 한 줄 문자열(개행 없음). 순수 함수 — 예외를 던지지 않는
        입력(빈 ``raw_commits``는 호출자 계약 위반이나, 방어적으로 총계
        표기만 ``<N raw>``로 두고 raw 커밋 목록은 빈 문자열이 된다).
    """
    is_multi = len(raw_commits) > 1
    total_marker = f"총 {total_raw}" if is_multi else f"{total_raw}"
    raw_part = "·".join(f"{sha}({d})" for sha, d in raw_commits)
    catalog_sha, catalog_date = catalog_commit
    body = (
        f"<{total_marker} raw> — raw 커밋 {raw_part} · "
        f"카탈로그 {catalog_sha}({catalog_date}) · 재시도 {retries}회"
    )
    # v2 log.md는 날짜·op를 엔트리 헤딩(`## [date] snapshot | ...`)이 담으므로
    # 요약 줄에는 접두를 빼고 넣는다(`with_prefix=False`).
    return f"{date} [snapshot] {body}" if with_prefix else body
