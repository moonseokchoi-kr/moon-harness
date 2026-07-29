"""hooks/lib/kompound_snapshot/registry.py — F7 registry 외과적 갱신 (arch §6.3.2/§6.3.3)

``wiki/sdd-spec-registry.md``를 **재생성하지 않고** 허용된 연산만 적용한다
(arch §6.3): ① 행 추가 ② 셀의 ``—`` → 링크 교체(``기타`` 열은 `` · `` 합성)
③ 열거된 카운트 문장 갱신, ④ (사용자 승인 2026-07-29 — arch §6.3.2 "방향 반전")
없는 kind 열 추가. 그 외 어떤 바이트도 건드리지 않는다 — 표 스키마가
heterogeneous(§6.3.2)라 파서는 열 역할을 **헤더 라벨**로 추론하고, 추론
실패 시 추측하지 않고 실패를 반환한다(``catalog_unparsed``).

이 모듈은 **텍스트 변환만** 한다(부작용 없음, arch §3.2 ``registry`` 행). 파일
IO·git 커밋은 호출자(T-10 ``apply.py``) 책임이다.

공개 API는 :func:`update_registry` 하나다. 입력·출력 계약은 arch에 구체
시그니처가 없어 이 태스크가 직접 결정했다(§ "설계 결정" 참조, 모듈 하단
docstring).

## 설계 결정 (arch에 없어 이 태스크가 직접 결정 — T-10이 참고할 것)

1. **입력 단위 = "신규(new)" raw 문서만.** F6 멱등에 의해 "갱신(updated)"된
   raw는 파일명이 이전과 동일하므로 registry 링크는 이미 올바르게 그 파일을
   가리키고 있다 — 구조적으로 손댈 것이 없다. 따라서 ``new_docs``에는
   **새로 생성된** raw 문서만 담는다(호출자가 F6 "신규"/"갱신" 카운트를
   이미 구분하고 있으므로 필터링 비용이 없다).
2. **엔트리 스키마** — 각 ``new_docs`` 원소는 다음 키를 갖는 매핑이다:
   ``{"repo_dir": str, "project": str, "feature": str, "kind": str,
   "raw_name": str, "worktree": Optional[str]}``.
   - ``repo_dir``: home repo 디렉토리 이름(스캔 레코드의 ``repo_dir`` basename).
     헤딩 매칭 후보이자 ``home repo``/``프로젝트`` 셀 값이다.
   - ``project``: ``prefix_map``으로 해석된 프리픽스(예: ``"acme"``). 헤딩
     매칭의 두 번째 후보다.
   - ``feature``/``kind``: naming.py가 소비한 것과 동일한 값(kind는 scan.py의
     ``KINDS`` 매핑 후 값 — spec/arch/ui/api/context/result 6종).
   - ``raw_name``: naming.py ``name_document()``가 반환한 값
     (``"raw/<project>-<feature>-<kind>.md"``, 접두 ``raw/`` 유무 무관 —
     이 모듈이 ``Path(...).name``으로 정규화한다).
   - ``worktree``: 이 사본이 워크트리에서 왔으면 워크트리 디렉토리 이름,
     아니면 ``None``.
3. **카운트 문장 갱신은 opt-in.** ``totals``(kwarg)를 생략(``None``)하면 이
   함수는 표 구조만 갱신하고 §6.3.3의 카운트 문장 2종은 건드리지 않는다.
   ``totals``를 주면 정확히 그 값으로 두 문장을 갱신한다. 총계 계산(스냅샷
   집합 정의 §6.3.1 포함)은 이 모듈의 책임이 아니다 — verify.py/apply.py가
   계산해 전달한다(이 모듈은 텍스트 변환만 한다는 arch §3.2 계약 유지).
4. **``기타`` 열은 ui/api/context 3종의 통합 열이다**(실측,
   `marvelous_kompound/wiki/sdd-spec-registry.md` L21 — 셀 예시
   ``[api](...) · [context](...)``). "없는 kind 열 추가"가 실제로 추가하는
   열은 항상 ``기타`` 하나뿐이다 — ui/api/context 각각의 전용 열은 실측
   registry에 존재하지 않는다.
5. **행 삽입 위치**: ``프로젝트`` 열이 있는 표(형상 (c))에서는 **같은 프로젝트
   행 그룹의 마지막 뒤**에 삽입한다(전체 표의 마지막이 아니다 — 실측
   `moon-harness` 3행이 그 그룹으로 뭉쳐 있다, registry L75-77). 그 외
   표에서는 표 전체가 한 프로젝트 소유이므로 표의 마지막 행 뒤 == 그룹의
   마지막 뒤로 일치한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

__all__ = ["update_registry"]

# ── 상수 (arch §6.3.2/§6.3.3) ────────────────────────────────────────────────

DIRECT_KINDS: Tuple[str, ...] = ("spec", "arch", "result")
MERGED_KINDS: Tuple[str, ...] = ("ui", "api", "context")  # → `기타` 열, 이 순서로 합성
ALLOWED_KINDS: Tuple[str, ...] = DIRECT_KINDS + MERGED_KINDS

PROJECT_COLUMN = "프로젝트"
EXTRA_COLUMN = "기타"
FEATURE_COLUMN = "feature"
EXISTING_WIKI_COLUMN = "기존 위키"
HOME_REPO_COLUMN = "home repo"

REQUIRED_BASE_COLUMNS: Tuple[str, ...] = (
    FEATURE_COLUMN,
    "spec",
    "arch",
    "result",
    EXISTING_WIKI_COLUMN,
    HOME_REPO_COLUMN,
)

# 실측 3형상(arch §6.3.2) — 열 추가 안전조건 (b)가 참조하는 "인지된 형상".
SHAPE_A: Tuple[str, ...] = (
    FEATURE_COLUMN, "spec", "arch", EXTRA_COLUMN, "result",
    EXISTING_WIKI_COLUMN, HOME_REPO_COLUMN,
)
SHAPE_B: Tuple[str, ...] = (
    FEATURE_COLUMN, "spec", "arch", "result",
    EXISTING_WIKI_COLUMN, HOME_REPO_COLUMN,
)
SHAPE_C: Tuple[str, ...] = (
    PROJECT_COLUMN, FEATURE_COLUMN, "spec", "arch", EXTRA_COLUMN, "result",
    EXISTING_WIKI_COLUMN, HOME_REPO_COLUMN,
)
RECOGNIZED_SHAPES: Tuple[Tuple[str, ...], ...] = (SHAPE_A, SHAPE_B, SHAPE_C)

# 새 프로젝트 신설(③) 시 사용하는 표 골격 — 실측 registry L21-22와 바이트 일치.
_NEW_TABLE_HEADER = "| " + " | ".join(SHAPE_A) + " |"
_NEW_TABLE_SEPARATOR = "|---------|:--:|:--:|:--:|:--:|------|-----------|"

_DECISIONS_HEADING = "## 결정과 근거"
_CURRENT_STATUS_HEADING = "## 현재 상태"
_RELATED_DOCS_HEADING = "## 관련 문서"

_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
_EXTRA_ENTRY_RE = re.compile(r"\[(ui|api|context)\]\(([^)]+)\)")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# §6.3.3 화이트리스트 정규식 2종 — 이 2개 형태에만 매칭되고, 매칭되면 그 줄만
# 손댄다. 그 외 줄(날짜 박힌 스냅샷 서술·산문 카운트 등)은 애초에 매칭되지
# 않으므로 불변이다.
_CURRENT_STATUS_RE = re.compile(
    r"^(\d+) feature · raw (\d+)개\(spec (\d+) · arch (\d+) · result (\d+) · "
    r"api (\d+) · ui (\d+) · context (\d+)\)\. 범례: ✓=있음, —=산출물 없음\.$"
)
_RAW_TOTAL_RE = re.compile(
    r"^- raw: `raw/<project>-<feature>-<kind>\.md` (\d+)개 \(위 표 링크\)$"
)


# ── 내부 자료구조 ────────────────────────────────────────────────────────────


@dataclass
class _Table:
    heading: Optional[str]
    header_idx: int
    separator_idx: int
    row_idxs: List[int] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)


# ── 라인 단위 파싱 헬퍼 ──────────────────────────────────────────────────────


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return len(s) >= 2 and s.startswith("|") and s.endswith("|")


def _split_row(line: str) -> List[str]:
    """행을 셀 문자열 리스트로 분해한다(양쪽 공백 트림, 선행/후행 빈 셀 제거).

    읽기(매칭)용 — 재구성에는 :func:`_replace_cell_in_line`/
    :func:`_insert_column_in_line`(원본 세그먼트 보존)을 쓴다.
    """
    parts = line.strip().split("|")
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _is_separator_row(line: str) -> bool:
    if not _is_table_row(line):
        return False
    cells = _split_row(line)
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(c) for c in cells)


def _replace_cell_in_line(line: str, col_index: int, new_value: str) -> str:
    """``col_index`` 번째 셀만 교체한다. 다른 셀의 원본 공백/문자는 보존."""
    segments = line.split("|")
    inner = segments[1:-1]
    inner[col_index] = f" {new_value} "
    return segments[0] + "|" + "|".join(inner) + "|" + segments[-1]


def _insert_column_in_line(line: str, col_index: int, new_cell_text: str) -> str:
    """``col_index`` 위치에 새 셀을 삽입한다(열 추가 — 헤더/구분선/데이터 행 공용)."""
    segments = line.split("|")
    inner = segments[1:-1]
    inner.insert(col_index, new_cell_text)
    return segments[0] + "|" + "|".join(inner) + "|" + segments[-1]


def _parse_tables(lines: Sequence[str]) -> List[_Table]:
    """``lines`` 전체를 스캔해 마크다운 표를 전부 찾는다.

    각 표에 가장 가까운 선행 ``### `` 헤딩 텍스트를 연결한다(``## ``나 다른
    헤딩이 사이에 없으면). 헤딩이 전혀 없으면 ``heading=None``.
    """
    tables: List[_Table] = []
    last_heading: Optional[str] = None
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("### "):
            last_heading = stripped[4:].strip()
            i += 1
            continue
        if stripped.startswith("## "):
            last_heading = None
            i += 1
            continue
        if _is_table_row(line) and i + 1 < n and _is_separator_row(lines[i + 1]):
            header_idx = i
            separator_idx = i + 1
            columns = _split_row(line)
            row_idxs: List[int] = []
            j = separator_idx + 1
            while j < n and _is_table_row(lines[j]):
                row_idxs.append(j)
                j += 1
            tables.append(
                _Table(
                    heading=last_heading,
                    header_idx=header_idx,
                    separator_idx=separator_idx,
                    row_idxs=row_idxs,
                    columns=columns,
                )
            )
            i = j
            continue
        i += 1
    return tables


# ── 3단 표 탐색 (arch §6.3.2, A-3 정정) ──────────────────────────────────────


def _candidates(repo_dir: str, project: str) -> List[str]:
    out: List[str] = []
    for c in (repo_dir, project):
        if c and c not in out:
            out.append(c)
    return out


def _stage1_heading_match(
    tables: Sequence[_Table], candidates: Sequence[str]
) -> Tuple[Optional[int], Optional[str]]:
    """섹션 헤딩(`### ...`) 부분 일치(대소문자 무시). 모호=매칭 섹션 개수 기준."""
    best_by_table: Dict[int, int] = {}
    for idx, table in enumerate(tables):
        if not table.heading:
            continue
        heading_low = table.heading.casefold()
        best = 0
        for cand in candidates:
            cand_low = cand.casefold()
            if cand_low and cand_low in heading_low:
                best = max(best, len(cand))
        if best > 0:
            best_by_table[idx] = best

    if not best_by_table:
        return None, None

    max_len = max(best_by_table.values())
    winners = [idx for idx, ln in best_by_table.items() if ln == max_len]
    if len(winners) > 1:
        return None, "ambiguous"
    return winners[0], None


def _stage2_project_column_match(
    tables: Sequence[_Table], lines: Sequence[str], candidates: Sequence[str]
) -> Tuple[Optional[int], Optional[str]]:
    """``프로젝트`` 열을 가진 표에서 그 값이 이미 존재하는 행을 찾는다."""
    best_by_table: Dict[int, int] = {}
    for idx, table in enumerate(tables):
        if PROJECT_COLUMN not in table.columns:
            continue
        proj_idx = table.columns.index(PROJECT_COLUMN)
        best = 0
        for row_idx in table.row_idxs:
            cells = _split_row(lines[row_idx])
            if proj_idx >= len(cells):
                continue
            cell_val = cells[proj_idx].casefold()
            for cand in candidates:
                cand_low = cand.casefold()
                if cand_low and cell_val == cand_low:
                    best = max(best, len(cand))
        if best > 0:
            best_by_table[idx] = best

    if not best_by_table:
        return None, None

    max_len = max(best_by_table.values())
    winners = [idx for idx, ln in best_by_table.items() if ln == max_len]
    if len(winners) > 1:
        return None, "ambiguous"
    return winners[0], None


def _locate_table(
    tables: Sequence[_Table], lines: Sequence[str], candidates: Sequence[str]
) -> Tuple[Optional[int], str]:
    """3단 탐색. 반환: ``(table_idx 또는 None, method)``.

    ``method`` ∈ {"heading", "project_column", "not_found",
    "ambiguous_heading", "ambiguous_project_column"}.
    """
    idx, reason = _stage1_heading_match(tables, candidates)
    if idx is not None:
        return idx, "heading"
    if reason == "ambiguous":
        return None, "ambiguous_heading"

    idx, reason = _stage2_project_column_match(tables, lines, candidates)
    if idx is not None:
        return idx, "project_column"
    if reason == "ambiguous":
        return None, "ambiguous_project_column"

    return None, "not_found"


# ── 셀 합성 헬퍼 ─────────────────────────────────────────────────────────────


def _direct_cell(raw_name: str) -> str:
    return f"[✓](../raw/{raw_name})"


def _merge_extra_cell(existing_cell: str, new_links: Mapping[str, str]) -> str:
    """``기타`` 셀에 ui/api/context 링크를 고정 순서로 합성한다(§6.3의 ` · ` 합성)."""
    entries: Dict[str, str] = {}
    if existing_cell and existing_cell != "—":
        for m in _EXTRA_ENTRY_RE.finditer(existing_cell):
            entries[m.group(1)] = m.group(2)
    for kind, raw_name in new_links.items():
        entries[kind] = f"../raw/{raw_name}"
    if not entries:
        return "—"
    ordered = [k for k in MERGED_KINDS if k in entries]
    return " · ".join(f"[{k}]({entries[k]})" for k in ordered)


def _home_repo_value(repo_dir: str, worktree: Optional[str]) -> str:
    if worktree:
        return f"{repo_dir} + `worktrees/{worktree}`"
    return repo_dir


# ── 행/열 조작 ───────────────────────────────────────────────────────────────


def _insertion_position(
    table: _Table, lines: Sequence[str], candidates: Sequence[str]
) -> int:
    """새 행을 넣을 라인 인덱스. `프로젝트` 열이 있으면 같은 그룹 마지막 뒤."""
    if PROJECT_COLUMN in table.columns and table.row_idxs:
        proj_idx = table.columns.index(PROJECT_COLUMN)
        group_rows = []
        for r in table.row_idxs:
            cells = _split_row(lines[r])
            if proj_idx >= len(cells):
                continue
            cell_val = cells[proj_idx].casefold()
            if any(cell_val == c.casefold() for c in candidates if c):
                group_rows.append(r)
        if group_rows:
            return max(group_rows) + 1

    if table.row_idxs:
        return table.row_idxs[-1] + 1
    return table.separator_idx + 1


def _build_row_cells(
    columns: Sequence[str],
    repo_dir: str,
    feature: str,
    direct_updates: Mapping[str, str],
    merged_updates: Mapping[str, str],
    worktree: Optional[str],
) -> List[str]:
    home_repo = _home_repo_value(repo_dir, worktree)
    cells: List[str] = []
    for col in columns:
        if col == FEATURE_COLUMN:
            cells.append(feature)
        elif col == PROJECT_COLUMN:
            cells.append(repo_dir)
        elif col in DIRECT_KINDS:
            cells.append(_direct_cell(direct_updates[col]) if col in direct_updates else "—")
        elif col == EXTRA_COLUMN:
            cells.append(_merge_extra_cell("—", merged_updates))
        elif col == EXISTING_WIKI_COLUMN:
            cells.append("—")
        elif col == HOME_REPO_COLUMN:
            cells.append(home_repo)
        else:  # pragma: no cover — 인지된 3형상 밖 열은 여기 도달하지 않는다
            cells.append("—")
    return cells


def _insert_new_row(
    lines: List[str],
    table: _Table,
    candidates: Sequence[str],
    repo_dir: str,
    feature: str,
    direct_updates: Mapping[str, str],
    merged_updates: Mapping[str, str],
    worktree: Optional[str],
) -> List[str]:
    cells = _build_row_cells(table.columns, repo_dir, feature, direct_updates, merged_updates, worktree)
    new_row = "| " + " | ".join(cells) + " |"
    insert_at = _insertion_position(table, lines, candidates)
    new_lines = list(lines)
    new_lines.insert(insert_at, new_row)
    return new_lines


def _update_existing_row(
    lines: List[str],
    table: _Table,
    row_idx: int,
    direct_updates: Mapping[str, str],
    merged_updates: Mapping[str, str],
) -> Tuple[List[str], int]:
    updated = 0
    line = lines[row_idx]
    cells = _split_row(line)

    for kind, raw_name in direct_updates.items():
        col_idx = table.columns.index(kind)
        current = cells[col_idx] if col_idx < len(cells) else "—"
        if current == "—":
            line = _replace_cell_in_line(line, col_idx, _direct_cell(raw_name))
            cells = _split_row(line)
            updated += 1
        # 이미 링크가 있으면(신규가 아닌 문서가 잘못 전달된 방어적 케이스) 손대지 않는다.

    if merged_updates:
        col_idx = table.columns.index(EXTRA_COLUMN)
        current = cells[col_idx] if col_idx < len(cells) else "—"
        new_val = _merge_extra_cell(current, merged_updates)
        if new_val != current:
            line = _replace_cell_in_line(line, col_idx, new_val)
            cells = _split_row(line)
            updated += 1

    new_lines = list(lines)
    new_lines[row_idx] = line
    return new_lines, updated


def _add_extra_column(lines: List[str], table: _Table) -> List[str]:
    insert_at = table.columns.index("arch") + 1
    new_lines = list(lines)
    new_lines[table.header_idx] = _insert_column_in_line(lines[table.header_idx], insert_at, " 기타 ")
    new_lines[table.separator_idx] = _insert_column_in_line(lines[table.separator_idx], insert_at, ":--:")
    for r in table.row_idxs:
        new_lines[r] = _insert_column_in_line(lines[r], insert_at, " — ")
    table.columns.insert(insert_at, EXTRA_COLUMN)
    return new_lines


def _create_new_section(
    lines: List[str], repo_dir: str, feature: str,
    direct_updates: Mapping[str, str], merged_updates: Mapping[str, str],
    worktree: Optional[str],
) -> Dict[str, Any]:
    insert_idx = None
    for i, line in enumerate(lines):
        if line.strip() == _DECISIONS_HEADING:
            insert_idx = i
            break
    if insert_idx is None:
        return {
            "ok": False,
            "reason": "catalog_unparsed",
            "detail": f"'{_DECISIONS_HEADING}' heading not found — cannot place new project section",
        }

    row_cells = _build_row_cells(SHAPE_A, repo_dir, feature, direct_updates, merged_updates, worktree)
    row_line = "| " + " | ".join(row_cells) + " |"

    new_block = ["", f"### {repo_dir}", "", _NEW_TABLE_HEADER, _NEW_TABLE_SEPARATOR, row_line, ""]
    new_lines = lines[:insert_idx] + new_block + lines[insert_idx:]
    return {"ok": True, "lines": new_lines}


# ── 카운트 문장 갱신 (arch §6.3.3, 화이트리스트) ─────────────────────────────


def _update_current_status(lines: List[str], totals: Mapping[str, int]) -> Tuple[List[str], Optional[str]]:
    heading_idx = None
    for i, line in enumerate(lines):
        if line.strip() == _CURRENT_STATUS_HEADING:
            heading_idx = i
            break
    if heading_idx is None:
        return lines, "not_found"

    j = heading_idx + 1
    while j < len(lines) and lines[j].strip() == "":
        j += 1
    if j >= len(lines):
        return lines, "not_found"

    line = lines[j]
    if not _CURRENT_STATUS_RE.match(line.strip()):
        return lines, "not_found"
    if _DATE_RE.search(line):
        # 화이트리스트에 매칭되더라도 날짜가 있으면 불변(보조 방어, §6.3.3 우선순위②).
        return lines, None

    leading_ws = line[: len(line) - len(line.lstrip())]
    new_text = (
        f"{totals['features']} feature · raw {totals['raw']}개"
        f"(spec {totals['spec']} · arch {totals['arch']} · result {totals['result']} · "
        f"api {totals['api']} · ui {totals['ui']} · context {totals['context']}). "
        f"범례: ✓=있음, —=산출물 없음."
    )
    new_lines = list(lines)
    new_lines[j] = leading_ws + new_text
    return new_lines, "updated"


def _update_raw_total(lines: List[str], totals: Mapping[str, int]) -> Tuple[List[str], Optional[str]]:
    heading_idx = None
    for i, line in enumerate(lines):
        if line.strip() == _RELATED_DOCS_HEADING:
            heading_idx = i
            break
    if heading_idx is None:
        return lines, "not_found"

    end = len(lines)
    for i in range(heading_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break

    for i in range(heading_idx + 1, end):
        line = lines[i]
        if not _RAW_TOTAL_RE.match(line.strip()):
            continue
        if _DATE_RE.search(line):
            return lines, None
        leading_ws = line[: len(line) - len(line.lstrip())]
        new_line = leading_ws + f"- raw: `raw/<project>-<feature>-<kind>.md` {totals['raw']}개 (위 표 링크)"
        new_lines = list(lines)
        new_lines[i] = new_line
        return new_lines, "updated"

    return lines, "not_found"


# ── 그룹핑 ───────────────────────────────────────────────────────────────────


def _group_entries(new_docs: Sequence[Mapping[str, Any]]) -> "Dict[str, Dict[str, Any]]":
    groups: Dict[str, Dict[str, Any]] = {}
    for doc in new_docs:
        repo_dir = doc["repo_dir"]
        project = doc["project"]
        feature = doc["feature"]
        kind = doc["kind"]
        raw_name = Path(doc["raw_name"]).name
        worktree = doc.get("worktree")

        g = groups.setdefault(repo_dir, {"project": project, "features": {}})
        f = g["features"].setdefault(feature, {"kinds": {}, "worktree": worktree})
        f["kinds"][kind] = raw_name
        if worktree and not f.get("worktree"):
            f["worktree"] = worktree
    return groups


# ── 공개 API ─────────────────────────────────────────────────────────────────


def update_registry(
    registry_text: str,
    new_docs: Sequence[Mapping[str, Any]],
    *,
    prefix_map: Mapping[str, Optional[str]],
    totals: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    """registry 텍스트를 외과적으로 갱신한다(arch §6.3/§6.3.2/§6.3.3).

    Args:
        registry_text: 현재 ``wiki/sdd-spec-registry.md`` 전체 텍스트.
        new_docs: 이번 배치에서 **신규로** raw에 복사된 문서 목록(모듈
            docstring "설계 결정" #2 스키마). 빈 시퀀스면 무변경으로
            즉시 반환한다(F7 "0건 스킵"과 일관).
        prefix_map: 현재 호출에서는 사용하지 않는다(각 엔트리가 이미
            해석된 ``project``를 담고 있어 재조회가 불필요) — arch §3.2
            계약 표와의 시그니처 정합을 위해 키워드로만 받는다.
        totals: 주어지면 §6.3.3의 카운트 문장 2종을 이 값으로 갱신한다.
            생략(``None``)하면 표만 갱신하고 카운트 문장은 손대지 않는다.

    Returns:
        성공: ``{"ok": True, "text": str, "rows_added": int,
        "cells_updated": int, "columns_added": [(heading, col), ...]}``.
        실패(추론 실패·모호·안전조건 미충족·화이트리스트 미인식):
        ``{"ok": False, "reason": "catalog_unparsed", "detail": str}``.
        예외를 던지지 않는다(F13 fail-safe) — 예기치 못한 오류도 위
        실패 모양으로 흡수한다.
    """
    try:
        return _update_registry_impl(registry_text, new_docs, totals=totals)
    except Exception as exc:  # noqa: BLE001 — fail-safe, 밖으로 던지지 않는다
        return {"ok": False, "reason": "catalog_unparsed", "detail": f"unexpected error: {exc}"}


def _update_registry_impl(
    registry_text: str,
    new_docs: Sequence[Mapping[str, Any]],
    *,
    totals: Optional[Mapping[str, int]],
) -> Dict[str, Any]:
    if not new_docs:
        return {"ok": True, "text": registry_text, "rows_added": 0, "cells_updated": 0, "columns_added": []}

    for doc in new_docs:
        if doc["kind"] not in ALLOWED_KINDS:
            return {
                "ok": False,
                "reason": "catalog_unparsed",
                "detail": f"unrecognized kind: {doc['kind']!r}",
            }

    trailing_newline = registry_text.endswith("\n")
    lines: List[str] = registry_text.splitlines()

    groups = _group_entries(new_docs)

    rows_added = 0
    cells_updated = 0
    columns_added: List[Tuple[Optional[str], str]] = []

    for repo_dir in sorted(groups):
        group = groups[repo_dir]
        project = group["project"]
        candidates = _candidates(repo_dir, project)

        for feature in sorted(group["features"]):
            finfo = group["features"][feature]
            kinds: Dict[str, str] = finfo["kinds"]
            worktree = finfo.get("worktree")
            direct_updates = {k: v for k, v in kinds.items() if k in DIRECT_KINDS}
            merged_updates = {k: v for k, v in kinds.items() if k in MERGED_KINDS}

            tables = _parse_tables(lines)
            table_idx, method = _locate_table(tables, lines, candidates)

            if method in ("ambiguous_heading", "ambiguous_project_column"):
                return {
                    "ok": False,
                    "reason": "catalog_unparsed",
                    "detail": f"registry section ambiguous for {repo_dir!r} ({method})",
                }

            if table_idx is None:
                result = _create_new_section(lines, repo_dir, feature, direct_updates, merged_updates, worktree)
                if not result["ok"]:
                    return result
                lines = result["lines"]
                rows_added += 1
                continue

            table = tables[table_idx]
            missing_required = [name for name in REQUIRED_BASE_COLUMNS if name not in table.columns]
            if missing_required:
                return {
                    "ok": False,
                    "reason": "catalog_unparsed",
                    "detail": f"table for {repo_dir!r} missing base columns: {missing_required}",
                }

            if merged_updates and EXTRA_COLUMN not in table.columns:
                shape_ok = tuple(table.columns) in RECOGNIZED_SHAPES
                if not shape_ok:
                    return {
                        "ok": False,
                        "reason": "catalog_unparsed",
                        "detail": (
                            f"cannot add '{EXTRA_COLUMN}' column for {repo_dir!r}: "
                            f"unrecognized table shape {tuple(table.columns)!r}"
                        ),
                    }
                lines = _add_extra_column(lines, table)
                columns_added.append((table.heading, EXTRA_COLUMN))

            feature_col = table.columns.index(FEATURE_COLUMN)
            existing_row_idx = None
            for r in table.row_idxs:
                cells = _split_row(lines[r])
                if feature_col < len(cells) and cells[feature_col] == feature:
                    existing_row_idx = r
                    break

            if existing_row_idx is not None:
                lines, updated = _update_existing_row(lines, table, existing_row_idx, direct_updates, merged_updates)
                cells_updated += updated
            else:
                lines = _insert_new_row(
                    lines, table, candidates, repo_dir, feature, direct_updates, merged_updates, worktree
                )
                rows_added += 1

    if totals is not None:
        lines, status1 = _update_current_status(lines, totals)
        if status1 == "not_found":
            return {
                "ok": False,
                "reason": "catalog_unparsed",
                "detail": "current-status count sentence not recognized",
            }
        lines, status2 = _update_raw_total(lines, totals)
        if status2 == "not_found":
            return {
                "ok": False,
                "reason": "catalog_unparsed",
                "detail": "raw-total count sentence not recognized",
            }

    text = "\n".join(lines) + ("\n" if trailing_newline else "")
    return {
        "ok": True,
        "text": text,
        "rows_added": rows_added,
        "cells_updated": cells_updated,
        "columns_added": columns_added,
    }
