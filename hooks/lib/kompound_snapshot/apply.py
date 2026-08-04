"""hooks/lib/kompound_snapshot/apply.py — F6 멱등 적용 + (i)/(ii) 커밋 경계 (arch §6.3.0).

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md`
(이하 "arch") §6.3.0((i)/(ii) 2단 분리·커밋 경계·F9 자기오염 회피·log 1줄 규칙)
· §6.3(트랜잭션 저널·부분 롤백) · §5.2.4(3축 원칙) · §6.2(JSON 스키마)
· §6.3.1(snapshot_set_rule) · §3.2(모듈 계약 표 `apply` 행).
spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` F6(멱등성) 중심,
F5(dedup mtime 채택)·F7(registry 갱신)·F8(검증 게이트)·F9(dirty/diverge) 연동.

## 이 모듈이 하는 일

1. **(i) raw 복사** — canonical 문서를 `raw/<project>-<feature>-<kind>.md`로
   verbatim 복사한다(F6: 없으면 신규 / 같으면 무동작·무로그 / 다르면 갱신).
   성공하면 **즉시 raw만 커밋**한다(`git_state.commit_raw`) — 워킹트리를
   clean하게 유지해 F9 자기 오염을 회피한다(arch §6.3.0).
2. **(ii) 카탈로그 갱신** — registry(`registry.py`) + index/log(`wiki_log.py`)를
   갱신하고 F8 게이트 3종(`verify.py`)을 통과해야만 커밋한다. 실패하면
   **카탈로그 변경만 롤백**하고 raw는 그대로 유지한다(이미 커밋됨).

두 단계의 성공/실패는 `raw_stage`/`catalog_stage` **독립 필드**로 보고한다
(arch §6.2 — 합치면 A-5 이전 함정으로 회귀).

## 공개 API

    apply(kompound_repo, canonical_records, *, prefix_map, scan_root=None,
          project_root=None) -> dict

반환 스키마::

    {
      "busy": bool,                    # 배타 락 획득 실패 — (i)(ii) 모두 미시도
      "precondition_failed": bool,     # F9 dirty/diverge — (i)(ii) 모두 미시도
      "precondition": dict | None,     # git_state.check_preconditions() 원본
                                        # (실제로 평가됐을 때만 non-None — busy
                                        # 케이스에서는 평가 자체를 안 하므로 None)
      "unmapped": [str, ...],          # F12 — 프리픽스 미등록 repo_dir 목록
      "dirty": [str, ...],             # precondition_failed 중 dirty 사유일 때
                                        # 파일 목록(그 외에는 빈 리스트)
      "raw_name_conflicts": [ {...} ], # C-6 — 감지된 raw_name 충돌(빈 리스트 가능)
      "raw_stage":     {"ok", "new", "updated", "unchanged",
                         "committed", "commit", "error"},       # arch §6.2
      "catalog_stage": {"ok", "attempted", "registry", "index", "log",
                         "committed", "commit", "failed_gates",
                         "unparsed", "error"},                  # arch §6.2
    }

`canonical_records`는 `dedup.dedup(scan.scan(...)["records"])`의 출력이다
(각 원소 `{"kind","path","md5","mtime","repo_dir"}`).

## Fail-safe 규약 (패키지 공통, F13)

`apply()`는 예외를 밖으로 던지지 않는다. 배타 락은 획득에 성공한 모든 경로에서
반드시 해제한다(`try/finally`) — 판정 도중 예외가 나도 락은 풀린다.

---

## 이월 실행 항목 처리 — 어디서 어떻게 (오케스트레이터 STATE 기준 5건)

### D-impl-1 — `new_docs`를 차집합으로 도출 (registry 영구 미링크 방지)

`_run_catalog_stage()`가 `new_docs`(→ `registry.update_registry`의 두 번째
인자)를 **F6 분류(new/updated)가 아니라**
`verify.snapshot_population(raw_dir, prefixes) -
verify.snapshot_registry_links(registry_text, prefixes)`(= T-9가 F8
게이트(2)에서 쓰는 것과 동일한 `missing` 집합)로 계산한다. 이 집합이 비어
있으면(모두 링크됨) 카탈로그 단계 자체를 스킵한다(`verify.should_run_gates`에
`{"new": missing, "updated": []}`를 먹여 재사용 — 라이브 raw_stage가 아니라
이 파생 리스트를 넣는 것이 핵심. `should_run_gates`의 계약은 "이 모양의 dict를
받아 new/updated 비었는지만 본다"이므로 이 재사용은 계약 위반이 아니다).

이 정의 덕에 이번 실행의 `canonical_records`에 전혀 포함되지 않은 문서(예:
1차 실행에서 raw 커밋까지 됐지만 카탈로그가 실패해 다음 실행에서는 스캔
대상에서 벗어난 경우 · 사람이 수동으로 raw에 넣은 문서)도 **자기 치유적으로**
회수된다. `raw_name → {project,feature,kind,repo_dir,worktree}` 역파싱은
아래 "파일명 역파싱" 절 참조.

### C-4 — 같은 raw_name 수렴 시 mtime 최신본 채택

`_prepare_raw_writes()`가 이번 호출의 `canonical_records`를 naming 결과의
**raw 파일명(basename)** 기준으로 그룹핑한다. 그룹 크기가 1을 넘으면(=서로
다른 `(kind, md5)` 그룹이 naming 이후 같은 파일명으로 수렴 — dedup은 이 단계
이전이라 이걸 잡지 못한다) `sorted(records, key=lambda r: (-mtime, path))`로
정렬해 mtime이 가장 최신인 것을 승자로 채택한다(F5 acceptance 문언 그대로).
동률이면 `path` 문자열 순으로 결정적으로 해소한다(진짜 모호는 없다 — 항상
해소 가능).

### C-6 — raw_name 충돌 검출 (조용한 덮어쓰기 없음)

위 그룹핑에서 크기 > 1인 그룹마다 `raw_name_conflicts` 리스트에
`{"raw_name","chosen_path","chosen_mtime","discarded":[{"path","mtime"},...]}`
항목을 추가해 **항상 보고한다**(호출자가 리스트를 무시하지 않는 한 조용히
사라지지 않는다).

**어느 verdict로 처리했는가 + 근거**: 새 verdict를 만들지 않았고, 기존
verdict 중 어느 것으로도 **격상시키지 않았다** — 즉 이 상황은 자연히
`raw_stage.ok=True`로 남고(승자의 내용이 verbatim으로 정상 write·커밋된다),
그 결과 T-11이 매핑할 최종 verdict는 (다른 조건이 정상이라면) 그대로
`snapshotted`다. 근거: F5 acceptance 문언 자체가 "내용 상이 시 mtime 최신본을
채택한다"를 정상 동작으로 명시한다 — 이것은 실패가 아니라 스펙이 요구하는
결정이다. `write_failed`/`scan_error` 등으로 격상시키면 정상 스펙 이행을
차단으로 취급하는 A-5 이전 함정(§5.2.4 축1/축3 오분류)과 같은 모양이 된다.
"조용히 덮어쓰지 말라"는 요구는 **가시성**(리스트에 항상 기록) 문제이지
**차단 여부** 문제가 아니라고 판단했다 — `raw_name_conflicts`가 비어있지
않으면 호출자(T-11)가 human 리포트에 그대로 노출할 수 있다.

### C-7 — `totals`를 반드시 계산해 전달

`_compute_totals()`가 (이번 raw 쓰기 이후, 즉 최신 상태의)
`verify.snapshot_population(raw_dir, prefixes)` 전체를 훑어
`{"features","raw","spec","arch","result","api","ui","context"}`를 계산하고,
`_run_catalog_stage()`가 카탈로그를 시도할 때마다(스킵이 아닌 한) 항상 이
값을 `registry.update_registry(..., totals=totals)`에 전달한다. §6.3.1의
스냅샷 집합 정의를 그대로 재사용하므로 F8 게이트(2)가 보는 수와 어긋나지
않는다.

### F9 `precondition_failed` — 직접 재조립 금지

`git_state.check_preconditions()`가 반환하는 **`precondition_failed`
필드를 그대로 읽는다**(`if precondition["precondition_failed"]:`). `ok`·
`dirty`·`diverged`를 직접 조립하지 않는다 — 그렇게 하면 `git_state.py`
docstring이 경고하는 바로 그 함정(`ok=True`인데 `dirty=True`인 경우를
놓침)에 빠진다. `precondition_failed=True`이면 (i) raw 복사를 **시도조차
하지 않는다**(락만 잡은 채 바로 실패 결과를 반환).

## 파일명 역파싱 — naming.py/verify.matches_snapshot_rule과의 일관성

`missing` 집합의 각 원소는 파일명(`<project>-<feature>-<kind>.md`)뿐이고
출처 레코드(repo_dir·worktree)를 모른다. 두 경로로 엔트리를 만든다:

1. **rich 경로** — 이번 호출의 `canonical_records`에서 실제로 처리된
   문서(신규·갱신·무동작 전부, `_build_rich_map()`)라면 원본 레코드의
   `repo_dir`/`path`에서 `worktree`를 그대로 뽑는다. `feature`는
   `naming.name_document()`가 이미 결정한 것과 **동일한 값**을 얻어야
   하므로, 별도 정규식으로 재계산하지 않고 "이미 아는 `project`/`kind`를
   가지고 raw_name에서 접두/접미만 벗겨낸다"(`_feature_from_basename`) —
   naming.py가 만든 최종 문자열을 그대로 역산하므로 fold-중복 규칙까지
   자동으로 일치한다.
2. **폴백 경로** — rich 맵에 없는(다른 실행에서 이미 커밋됐거나 사람이
   수동으로 넣은) raw 파일은 `_decompose_raw_name()`으로 `(project, kind)`를
   추론한다. 이 함수는 **`verify.matches_snapshot_rule`과 정확히 같은
   판정식**(kind 접미사 매칭 + `<prefix>-` 시작 + 비어있지 않은 remainder)을
   쓴다 — 새 정규식을 만들지 않고 동일한 술어를 그대로 재구현한다(별도
   정규식을 쓰면 두 모듈의 판정이 갈릴 위험이 있다는 task 지시 반영). 여러
   프리픽스가 동시에 접두로 매칭될 수 있는 이론적 모호성은 **가장 긴
   프리픽스 우선**으로 결정적으로 해소한다(registry.py의 헤딩 매칭이 같은
   원칙을 쓰는 것과 동일선상). `repo_dir`은 알 수 없으므로 `project` 값으로
   대체한다(registry._candidates가 이미 `[repo_dir, project]` 둘 다 후보로
   쓰므로 project 하나만 있어도 헤딩 매칭은 정상 동작한다).

## arch에 없어 이 태스크가 직접 결정한 것

1. **`build_snapshot_log_line`의 `catalog_commit` sha**는 로그 줄 자체가
   그 커밋의 내용물(`log.md`)에 포함되므로 커밋 전에 실제 sha를 알 수
   없다(자기 참조 순환 — arch가 다루지 않은 문제). `--amend`로 사후 교정하면
   커밋이 2개가 아니라 사실상 3단계(쓰기·커밋·amend)가 되어 복잡도·롤백
   범위가 늘어난다. 이 태스크는 **`"HEAD"` 리터럴을 sha 자리에 넣는다** —
   `git log`로 그 시점의 실제 커밋을 사람이 즉시 식별할 수 있고, 정확한 sha
   문자열을 굳이 자기참조로 박아 넣을 필요가 없다고 판단했다(정보 손실 없음
   — 커밋 자체가 `HEAD`를 가리키는 시점의 로그이므로).
2. **raw 커밋 이력 발견은 `git log` 직접 조회로 한다**(새 영속 상태를 만들지
   않는다). "카탈로그가 여러 번 실패한 뒤 성공하면 그 사이 raw 커밋들을 전부
   열거한다"(arch §6.3.0 N-2)를 만족하려면 실행 간 raw 커밋 sha 목록을
   어딘가에 보관해야 하는데, 어느 모듈도 이 상태를 소유하지 않는다(git_state·
   runtime_state 둘 다 아님, 이 두 모듈은 T-10 소유가 아니라 수정 불가). git
   이력 자체가 이미 이 정보의 SSOT이므로(`snapshot(raw):`/`snapshot(catalog):`
   커밋 메시지 프리픽스), `_find_uncataloged_raw_commits()`가 마지막
   `snapshot(catalog):` 커밋 이후의 `snapshot(raw):` 커밋들을 시간순으로
   조회한다 — 별도 상태 없이 자기 치유적이다(D-impl-1과 같은 철학).
3. **`retries` 카운트**는 `max(0, len(raw_commits) - 1)`로 근사한다 — 정확한
   "카탈로그가 실패한 횟수"는 raw 변경 없이도 카탈로그만 재시도될 수 있어
   raw 커밋 수만으로는 완전히 정확하지 않지만(과소 계상 가능), 이 근사는
   ①추가 영속 상태 없이 ②git 이력만으로 ③단조 비감소로 계산 가능하다.
   정확한 카운트가 필요하면 `runtime_state`의 `catalog_lag_count`를
   호출자가 별도로 합성해 인간 리포트에 보완할 수 있다(이 함수의 반환값은
   log.md 한 줄 조립용 근사치일 뿐, 결정/차단 로직에는 전혀 쓰이지 않는다).
4. **`hook_line`/`recent_change_line`은 이 모듈이 조립한다**(wiki_log.py는
   "호출자가 완성된 문자열로 조립해 전달"하라고 명시했다, T-8 결정 #1). 내용은
   기계적 사실(날짜·건수·프로젝트 목록·총계)만 담고 "주제 합성"을 하지
   않는다(arch §1 원칙 2와 일관 — 이 훅은 판단하지 않는다).
5. **`project_root` 파라미터(선택)** — task 완료조건 8이 `apply()`가
   `runtime_state.record_apply_outcome(project_root, raw_ok=..., catalog_ok=...)`
   를 호출하도록 요구하지만, arch가 지정한 `apply()` 입력(§3.2)에는
   "canonical 리스트, kompound_repo"만 있고 `project_root`(SDD 프로젝트
   루트 — 런타임 상태 파일이 사는 곳)가 없다. `project_root`를 **선택
   키워드 인자**(기본 `None`)로 추가했다 — 생략하면 상태 기록을 건너뛴다(단위
   테스트에서 `project_root` 없이 순수하게 (i)/(ii) 로직만 검증할 수 있게
   하기 위함). `catalog_ok`는 "카탈로그를 시도했고 실패했을 때만" `False`다
   — 스킵(0건, `attempted=False`)은 "할 일이 없어 성공"으로 취급한다(그래야
   raw만 성공하고 볼 링크가 이미 다 있는 정상 케이스가 `DONE`이 된다).
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

from hooks.lib.kompound_snapshot import git_state, naming, registry, runtime_state, verify, wiki_log

__all__ = ["apply"]

PathLike = Union[str, "Path"]

_GIT_LOG_TIMEOUT_SECONDS = 30


# ── 기본 스테이지 shape 헬퍼 (arch §6.2 스키마) ──────────────────────────────


def _failed_raw_stage(error: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "new": [],
        "updated": [],
        "unchanged": 0,
        "committed": False,
        "commit": None,
        "error": error,
    }


def _empty_catalog_stage() -> Dict[str, Any]:
    """(i) 실패로 (ii)가 미시도됐거나, 카탈로그 링크 누락이 0건이라 스킵된 경우.

    ``attempted=False``는 실패가 아니다(F7/F8 "0건 스킵은 정상 종료") — 이
    shape의 ``ok=True``는 "여기까지는 아무 문제 없음"을 뜻한다.
    """
    return {
        "ok": True,
        "attempted": False,
        "registry": False,
        "index": False,
        "log": False,
        "committed": False,
        "commit": None,
        "failed_gates": [],
        "unparsed": None,
        "error": "",
    }


def _catalog_unparsed(detail: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "attempted": True,
        "registry": False,
        "index": False,
        "log": False,
        "committed": False,
        "commit": None,
        "failed_gates": [],
        "unparsed": detail,
        "error": detail,
    }


def _catalog_gate_failure(failed_gates: List[str], detail: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "attempted": True,
        "registry": False,
        "index": False,
        "log": False,
        "committed": False,
        "commit": None,
        "failed_gates": failed_gates,
        "unparsed": None,
        "error": detail,
    }


# ── 트랜잭션 저널 롤백 (arch §6.3 "단계별 저널") ─────────────────────────────

_JournalEntry = Tuple[Path, bool, Optional[bytes]]


def _rollback_journal(journal: Sequence[_JournalEntry]) -> None:
    """`(경로, 존재여부, 원본 바이트)` 저널을 역순으로 되돌린다.

    존재했던 파일은 원본 바이트로 복원하고, 새로 생겼던 파일은 삭제한다.
    최선을 다한 롤백이다(fail-safe) — 개별 항목의 복원 실패는 무시하고
    계속 진행한다(예외를 던지지 않는다).
    """
    for path, existed, original_bytes in reversed(list(journal)):
        try:
            if existed:
                if original_bytes is not None:
                    path.write_bytes(original_bytes)
            else:
                if path.exists():
                    path.unlink()
        except OSError:
            pass


# ── (i) raw 복사 — C-4/C-6 그룹핑 + F6 멱등 write ────────────────────────────


def _prepare_raw_writes(
    canonical_records: Sequence[Mapping[str, Any]],
    prefix_map: Mapping[str, Optional[str]],
    scan_root: Optional[str],
) -> Tuple[Dict[str, Mapping[str, Any]], List[str], List[Dict[str, Any]]]:
    """`canonical_records`를 naming 결과 파일명 기준으로 그룹핑하고,
    F12 미등록 문서 분리 + C-4/C-6(같은 raw_name 수렴) 해소를 수행한다.

    반환: ``(winners, unmapped, conflicts)`` — ``winners``는
    ``{basename: 승자 record}``, ``unmapped``는 프리픽스 미등록 ``repo_dir``
    목록(F12), ``conflicts``는 감지된 raw_name 충돌 목록(C-6, 모듈 docstring
    참조).
    """
    unmapped: List[str] = []
    by_basename: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)

    for record in canonical_records:
        naming_result = naming.name_document(record, prefix_map, scan_root)
        if "unmapped" in naming_result:
            unmapped.append(naming_result["unmapped"])
            continue
        basename = Path(naming_result["raw_name"]).name
        by_basename[basename].append(record)

    winners: Dict[str, Mapping[str, Any]] = {}
    conflicts: List[Dict[str, Any]] = []
    for basename in sorted(by_basename):
        records = by_basename[basename]
        if len(records) == 1:
            winners[basename] = records[0]
            continue
        # C-4: mtime 최신 채택. 동률은 path 문자열 순으로 결정적 해소.
        ordered = sorted(records, key=lambda r: (-float(r["mtime"]), str(r["path"])))
        winner = ordered[0]
        winners[basename] = winner
        conflicts.append(
            {
                "raw_name": basename,
                "chosen_path": winner["path"],
                "chosen_mtime": winner["mtime"],
                "discarded": [{"path": r["path"], "mtime": r["mtime"]} for r in ordered[1:]],
            }
        )
    return winners, unmapped, conflicts


def _write_raw_files(
    kompound_repo: PathLike, winners: Mapping[str, Mapping[str, Any]]
) -> Tuple[Dict[str, Any], List[_JournalEntry]]:
    """승자 레코드들을 `raw/`에 F6 규칙대로 verbatim 쓴다(신규/무동작/갱신).

    실패(IO 오류 등 어떤 예외든)하면 **이 함수 내부에서 즉시 저널을
    롤백**하고 ``journal=[]``(이미 되돌렸다는 뜻)와 실패 shape를 반환한다 —
    호출자가 부분 저널을 들고 있다가 롤백을 깜빡할 위험을 원천 차단한다.
    """
    raw_root = Path(kompound_repo) / "raw"
    journal: List[_JournalEntry] = []
    new_list: List[str] = []
    updated_list: List[str] = []
    unchanged_count = 0
    try:
        for basename in sorted(winners):
            record = winners[basename]
            target = raw_root / basename
            source_bytes = Path(record["path"]).read_bytes()

            existed = target.exists()
            if existed:
                original_bytes = target.read_bytes()
                if original_bytes == source_bytes:
                    unchanged_count += 1
                    continue  # F6: 내용 동일 — 완전 무동작·무로그
                journal.append((target, True, original_bytes))
                target.write_bytes(source_bytes)
                updated_list.append(basename)
            else:
                journal.append((target, False, None))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source_bytes)
                new_list.append(basename)

        return (
            {"ok": True, "new": new_list, "updated": updated_list, "unchanged": unchanged_count, "error": ""},
            journal,
        )
    except Exception as exc:  # noqa: BLE001 - fail-safe(F13): 전량 롤백 후 write_failed
        _rollback_journal(journal)
        return (
            {"ok": False, "new": [], "updated": [], "unchanged": 0, "error": f"raw write failed: {exc}"},
            [],
        )


def _worktree_name_from_path(path: str) -> Optional[str]:
    """`path`가 `*/worktrees/<name>/*` 세그먼트를 가지면 `<name>`을 반환한다
    (scan.py `_has_worktrees_segment`와 같은 세그먼트 인식 방식)."""
    parts = Path(path).parts
    if "worktrees" in parts:
        idx = parts.index("worktrees")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _feature_from_basename(basename: str, project: str, kind: str) -> Optional[str]:
    """이미 아는 `project`/`kind`를 가지고 raw 파일명에서 `<feature>`를
    역산한다(naming.py가 만든 최종 문자열을 그대로 벗겨내므로 fold-중복
    규칙까지 자동으로 일치한다 — 모듈 docstring "파일명 역파싱" 참조)."""
    if not basename.endswith(".md"):
        return None
    stem = basename[: -len(".md")]
    suffix = f"-{kind}"
    if not stem.endswith(suffix):
        return None
    remainder = stem[: -len(suffix)]
    head = f"{project}-"
    if not remainder.startswith(head) or len(remainder) <= len(head):
        return None
    return remainder[len(head) :]


def _build_rich_map(
    winners: Mapping[str, Mapping[str, Any]],
    prefix_map: Mapping[str, Optional[str]],
    scan_root: Optional[str],
) -> Dict[str, Dict[str, Any]]:
    """이번 호출에서 실제로 처리된(신규·갱신·무동작 전부) 승자 레코드들로부터
    registry 엔트리 스키마를 조립한다(모듈 docstring "rich 경로")."""
    rich_map: Dict[str, Dict[str, Any]] = {}
    for basename, record in winners.items():
        project = naming.resolve_prefix(record["repo_dir"], prefix_map, scan_root)
        if project is None:
            continue  # 이론상 도달 불가(winners는 이미 매핑된 것만) — 방어적 스킵
        kind = record["kind"]
        feature = _feature_from_basename(basename, project, kind)
        if feature is None:
            continue
        rich_map[basename] = {
            "repo_dir": Path(record["repo_dir"]).name,
            "project": project,
            "feature": feature,
            "kind": kind,
            "raw_name": f"raw/{basename}",
            "worktree": _worktree_name_from_path(record["path"]),
        }
    return rich_map


def _run_raw_stage(
    kompound_repo: PathLike,
    canonical_records: Sequence[Mapping[str, Any]],
    prefix_map: Mapping[str, Optional[str]],
    scan_root: Optional[str],
) -> Tuple[Dict[str, Any], List[str], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """(i) raw 복사 전체 — 준비 → write → 커밋. 실패 시 write_failed +
    전량 롤백(arch §6.3.0)."""
    winners, unmapped, conflicts = _prepare_raw_writes(canonical_records, prefix_map, scan_root)
    write_result, journal = _write_raw_files(kompound_repo, winners)

    if not write_result["ok"]:
        return _failed_raw_stage(write_result["error"]), unmapped, conflicts, {}

    commit_result = git_state.commit_raw(kompound_repo, len(write_result["new"]), len(write_result["updated"]))
    if not commit_result["ok"]:
        _rollback_journal(journal)
        return (
            _failed_raw_stage(f"commit failed: {commit_result['reason']}"),
            unmapped,
            conflicts,
            {},
        )

    raw_stage = {
        "ok": True,
        "new": write_result["new"],
        "updated": write_result["updated"],
        "unchanged": write_result["unchanged"],
        "committed": commit_result["committed"],
        "commit": commit_result["commit"],
        "error": "",
    }
    rich_map = _build_rich_map(winners, prefix_map, scan_root)
    return raw_stage, unmapped, conflicts, rich_map


# ── (ii) 카탈로그 갱신 — D-impl-1 missing 집합 + C-7 totals ──────────────────


def _decompose_raw_name(basename: str, prefixes: Sequence[str]) -> Optional[Tuple[str, str]]:
    """`verify.matches_snapshot_rule`과 정확히 같은 판정식으로 `(project,
    kind)`를 역추론한다(모듈 docstring "파일명 역파싱" 폴백 경로). 여러
    프리픽스가 동시에 접두 매칭되면 **가장 긴 것 우선**으로 결정적으로
    해소한다. 매칭 실패 시 `None`(예외를 던지지 않는다)."""
    if not basename.endswith(".md"):
        return None
    stem = basename[: -len(".md")]
    best: Optional[Tuple[int, str, str]] = None
    for kind in verify.KINDS:
        suffix = f"-{kind}"
        if not stem.endswith(suffix):
            continue
        remainder = stem[: -len(suffix)]
        for prefix in prefixes:
            head = f"{prefix}-"
            if remainder.startswith(head) and len(remainder) > len(head):
                candidate = (len(prefix), prefix, kind)
                if best is None or candidate[0] > best[0]:
                    best = candidate
    if best is None:
        return None
    _, prefix, kind = best
    return prefix, kind


def _reverse_parse_entry(basename: str, prefixes: Sequence[str]) -> Optional[Dict[str, Any]]:
    """rich 맵에 없는 raw 파일명을 registry 엔트리 스키마로 역파싱한다
    (D-impl-1 self-heal 폴백 — 다른 실행에서 이미 커밋됐거나 사람이 수동으로
    넣은 raw). `repo_dir`/`worktree`는 알 수 없으므로 `repo_dir=project`,
    `worktree=None`으로 대체한다(registry._candidates가 이미 project를
    후보로 쓰므로 헤딩 매칭은 정상 동작한다)."""
    decomposed = _decompose_raw_name(basename, prefixes)
    if decomposed is None:
        return None
    project, kind = decomposed
    feature = _feature_from_basename(basename, project, kind)
    if feature is None:
        return None
    return {
        "repo_dir": project,
        "project": project,
        "feature": feature,
        "kind": kind,
        "raw_name": f"raw/{basename}",
        "worktree": None,
    }


def _compute_totals(population: Set[str], prefixes: Sequence[str]) -> Dict[str, int]:
    """§6.3.1 스냅샷 집합 정의로 registry 카운트 문장 2종(§6.3.3)에 쓸
    총계를 계산한다(C-7). F8 게이트(2)와 같은 모집단을 쓰므로 두 수치가
    어긋나지 않는다."""
    counts: Dict[str, int] = {kind: 0 for kind in verify.KINDS}
    features: Set[Tuple[str, str]] = set()
    for basename in population:
        decomposed = _decompose_raw_name(basename, prefixes)
        if decomposed is None:
            continue  # population은 이미 matches_snapshot_rule을 만족 — 도달 불가, 방어적
        project, kind = decomposed
        feature = _feature_from_basename(basename, project, kind)
        if feature is None:
            continue
        counts[kind] += 1
        features.add((project, feature))
    return {
        "features": len(features),
        "raw": len(population),
        "spec": counts["spec"],
        "arch": counts["arch"],
        "result": counts["result"],
        "api": counts["api"],
        "ui": counts["ui"],
        "context": counts["context"],
    }


def _build_hook_line(totals: Mapping[str, int]) -> str:
    """index.md Entries의 `sdd-spec-registry` 훅 문장(기계적 사실만, 주제
    합성 없음 — arch §1 원칙 2)."""
    return (
        f"- [sdd-spec-registry](sdd-spec-registry.md) — SDD spec/design/result 카탈로그. "
        f"{totals['features']} feature · raw {totals['raw']}개."
    )


def _build_recent_change_line(date: str, new_docs: Sequence[Mapping[str, Any]], totals: Mapping[str, int]) -> str:
    """index.md 최근 변경 섹션에 prepend할 한 줄(기계적 사실만)."""
    projects = sorted({doc["project"] for doc in new_docs})
    proj_text = ", ".join(projects) if projects else "-"
    return f"- {date} [snapshot] {len(new_docs)}건 카탈로그 편입 ({proj_text}) — raw 총 {totals['raw']}개"


def _find_uncataloged_raw_commits(kompound_repo: PathLike) -> List[Tuple[str, str]]:
    """마지막 `snapshot(catalog):` 커밋 이후의 `snapshot(raw):` 커밋들을
    시간순(오래된 것 → 최신)으로 찾는다(모듈 docstring "arch에 없어 직접
    결정한 것" #2). git 이력 자체가 SSOT이므로 별도 영속 상태가 필요 없다.
    실패 시 빈 리스트(fail-safe) — `build_snapshot_log_line`이 빈 입력을
    이미 방어적으로 처리한다."""
    try:
        proc = subprocess.run(
            ["git", "log", "--format=%h%x01%as%x01%s"],
            cwd=str(kompound_repo),
            capture_output=True,
            text=True,
            timeout=_GIT_LOG_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0:
            return []
        raw_commits: List[Tuple[str, str]] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\x01")
            if len(parts) != 3:
                continue
            sha, date, subject = parts
            if subject.startswith("snapshot(catalog):"):
                break
            if subject.startswith("snapshot(raw):"):
                raw_commits.append((sha, date))
        raw_commits.reverse()
        return raw_commits
    except Exception:  # noqa: BLE001 - fail-safe(F13)
        return []


def _run_catalog_stage(
    kompound_repo: PathLike,
    prefix_map: Mapping[str, Optional[str]],
    rich_map: Mapping[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """(ii) 카탈로그 갱신 전체 — missing 집합 도출(D-impl-1) → 텍스트 변환
    (in-memory) → write → F8 게이트 → 커밋. 텍스트 변환 실패는 파일을 전혀
    건드리지 않으므로 롤백이 필요 없다. 실제 write 이후의 실패(게이트/커밋)만
    저널로 롤백한다."""
    journal: List[_JournalEntry] = []
    try:
        repo = Path(kompound_repo)
        prefixes = verify.effective_prefixes(prefix_map)

        registry_path = repo / "wiki" / "sdd-spec-registry.md"
        index_path = repo / "wiki" / "index.md"
        log_path = repo / "wiki" / "log.md"

        try:
            registry_text = registry_path.read_text(encoding="utf-8")
            index_text = index_path.read_text(encoding="utf-8")
            log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        except OSError as exc:
            return _catalog_unparsed(f"wiki 파일 읽기 실패: {exc}")

        raw_dir = repo / "raw"
        population = verify.snapshot_population(raw_dir, prefixes)
        registry_links = verify.snapshot_registry_links(registry_text, prefixes)
        missing = sorted(population - registry_links)  # D-impl-1 재정의

        # verify.should_run_gates는 "이 shape의 dict를 받아 new/updated가
        # 비었는지만 본다"는 계약이므로, 라이브 raw_stage가 아니라 D-impl-1
        # 파생 리스트를 먹여도 계약 위반이 아니다(모듈 docstring D-impl-1 절).
        if not verify.should_run_gates({"new": missing, "updated": []}):
            return _empty_catalog_stage()

        new_docs: List[Dict[str, Any]] = []
        for basename in missing:
            entry = rich_map.get(basename)
            if entry is None:
                entry = _reverse_parse_entry(basename, prefixes)
            if entry is None:
                continue  # 이론상 도달 불가(missing은 matches_snapshot_rule을 만족) — fail-safe 스킵
            new_docs.append(entry)

        totals = _compute_totals(population, prefixes)  # C-7: 항상 계산

        registry_result = registry.update_registry(registry_text, new_docs, prefix_map=prefix_map, totals=totals)
        if not registry_result["ok"]:
            return _catalog_unparsed(registry_result.get("detail", registry_result.get("reason", "")))

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        hook_line = _build_hook_line(totals)
        recent_change_line = _build_recent_change_line(today, new_docs, totals)

        index_result = wiki_log.update_index(index_text, hook_line=hook_line, recent_change_line=recent_change_line)
        if not index_result["ok"]:
            return _catalog_unparsed(index_result.get("detail", index_result.get("reason", "")))

        raw_commits = _find_uncataloged_raw_commits(repo)
        retries = max(0, len(raw_commits) - 1)
        log_line = wiki_log.build_snapshot_log_line(
            date=today,
            total_raw=len(new_docs),
            raw_commits=raw_commits if raw_commits else [("HEAD", today)],
            catalog_commit=("HEAD", today),
            retries=retries,
        )
        log_result = wiki_log.append_log(log_text, line=log_line)
        if not log_result["ok"]:
            return _catalog_unparsed(log_result.get("detail", log_result.get("reason", "")))

        # 지금부터 실제 디스크 쓰기 — 저널 생성 후 3파일 write.
        journal = [
            (registry_path, True, registry_text.encode("utf-8")),
            (index_path, True, index_text.encode("utf-8")),
            (log_path, log_path.exists(), log_text.encode("utf-8") if log_path.exists() else None),
        ]
        registry_path.write_text(registry_result["text"], encoding="utf-8")
        index_path.write_text(index_result["text"], encoding="utf-8")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(log_result["text"], encoding="utf-8")

        gates = verify.run_gates(kompound_repo, prefix_map)
        failed = [g for g in gates if not g["ok"]]
        if failed:
            _rollback_journal(journal)
            detail = "; ".join(g["detail"] for g in failed)
            return _catalog_gate_failure([g["gate"] for g in failed], detail)

        detail = f"{len(new_docs)}건 링크·카운트 갱신 (raw 총 {totals['raw']}개)"
        commit_result = git_state.commit_catalog(kompound_repo, detail)
        if not commit_result["ok"]:
            _rollback_journal(journal)
            return _catalog_unparsed(f"commit failed: {commit_result['reason']}")

        return {
            "ok": True,
            "attempted": True,
            "registry": True,
            "index": True,
            "log": True,
            "committed": commit_result["committed"],
            "commit": commit_result["commit"],
            "failed_gates": [],
            "unparsed": None,
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001 - fail-safe(F13)
        _rollback_journal(journal)
        return _catalog_unparsed(f"unexpected error: {exc}")


# ── 최상위 조립 — 배타 락 + 판정 순서 + runtime_state 반영 ───────────────────


def _finalize(
    project_root: Optional[PathLike],
    raw_stage: Dict[str, Any],
    catalog_stage: Dict[str, Any],
    *,
    busy: bool,
    precondition_failed: bool,
    precondition: Optional[Dict[str, Any]],
    unmapped: List[str],
    dirty: List[str],
    raw_name_conflicts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """공통 결과 조립 + (project_root가 주어졌다면) runtime_state 반영(완료
    조건 8). ``catalog_ok``는 "스킵(0건)"도 성공으로 친다 — 카탈로그가 정말
    실패했을 때(``attempted=True and ok=False``)만 `False`다."""
    if project_root is not None:
        raw_ok = bool(raw_stage.get("ok"))
        catalog_ok = (not catalog_stage.get("attempted")) or bool(catalog_stage.get("ok"))
        runtime_state.record_apply_outcome(project_root, raw_ok=raw_ok, catalog_ok=catalog_ok)

    return {
        "busy": busy,
        "precondition_failed": precondition_failed,
        "precondition": precondition,
        "unmapped": unmapped,
        "dirty": dirty,
        "raw_name_conflicts": raw_name_conflicts,
        "raw_stage": raw_stage,
        "catalog_stage": catalog_stage,
    }


def _apply_impl(
    kompound_repo: PathLike,
    canonical_records: Sequence[Mapping[str, Any]],
    *,
    prefix_map: Mapping[str, Optional[str]],
    scan_root: Optional[str],
    project_root: Optional[PathLike],
) -> Dict[str, Any]:
    lock_result = git_state.acquire_lock(kompound_repo)
    if not lock_result.get("ok") or not lock_result.get("acquired"):
        raw_stage = _failed_raw_stage(f"busy: {lock_result.get('reason', 'unknown')}")
        return _finalize(
            project_root,
            raw_stage,
            _empty_catalog_stage(),
            busy=True,
            precondition_failed=False,
            precondition=None,
            unmapped=[],
            dirty=[],
            raw_name_conflicts=[],
        )

    try:
        try:
            # F9 선행 확인 — precondition_failed 결합 필드를 그대로 쓴다.
            # ok/dirty/diverged를 직접 재조립하지 않는다(모듈 docstring 참조).
            precondition = git_state.check_preconditions(kompound_repo)
            if precondition["precondition_failed"]:
                raw_stage = _failed_raw_stage(f"precondition_failed: {precondition.get('reason')}")
                return _finalize(
                    project_root,
                    raw_stage,
                    _empty_catalog_stage(),
                    busy=False,
                    precondition_failed=True,
                    precondition=precondition,
                    unmapped=[],
                    dirty=list(precondition.get("dirty_files") or []),
                    raw_name_conflicts=[],
                )

            raw_stage, unmapped, conflicts, rich_map = _run_raw_stage(
                kompound_repo, canonical_records, prefix_map, scan_root
            )
            if not raw_stage["ok"]:
                return _finalize(
                    project_root,
                    raw_stage,
                    _empty_catalog_stage(),
                    busy=False,
                    precondition_failed=False,
                    precondition=precondition,
                    unmapped=unmapped,
                    dirty=[],
                    raw_name_conflicts=conflicts,
                )

            catalog_stage = _run_catalog_stage(kompound_repo, prefix_map, rich_map)
            return _finalize(
                project_root,
                raw_stage,
                catalog_stage,
                busy=False,
                precondition_failed=False,
                precondition=precondition,
                unmapped=unmapped,
                dirty=[],
                raw_name_conflicts=conflicts,
            )
        except Exception as exc:  # noqa: BLE001 - fail-safe(F13), 락은 바깥 finally가 해제
            return _finalize(
                project_root,
                _failed_raw_stage(f"unexpected error: {exc}"),
                _empty_catalog_stage(),
                busy=False,
                precondition_failed=False,
                precondition=None,
                unmapped=[],
                dirty=[],
                raw_name_conflicts=[],
            )
    finally:
        git_state.release_lock(kompound_repo)


def apply(
    kompound_repo: PathLike,
    canonical_records: Sequence[Mapping[str, Any]],
    *,
    prefix_map: Mapping[str, Optional[str]],
    scan_root: Optional[str] = None,
    project_root: Optional[PathLike] = None,
) -> Dict[str, Any]:
    """F6 멱등 적용 — (i) raw 복사 + (ii) 카탈로그 갱신, 커밋 경계 분리
    (arch §6.3.0). 모듈 docstring 참조.

    Args:
        kompound_repo: kompound 저장소 절대경로.
        canonical_records: `dedup.dedup(scan.scan(...)["records"])` 출력.
        prefix_map: `config.resolve_config()["prefix_map"]`.
        scan_root: naming.py 완화 재조회용(arch §5.4.2 규칙5). 생략 가능.
        project_root: 주어지면 `runtime_state.record_apply_outcome()`으로
            (i)/(ii) 결과를 반영한다(완료조건 8). 생략하면 상태 기록 스킵.

    Returns:
        모듈 docstring "공개 API" 절의 스키마. 예외를 던지지 않는다(F13).
        배타 락은 획득에 성공한 모든 경로에서 반드시 해제된다.
    """
    try:
        return _apply_impl(
            kompound_repo,
            canonical_records,
            prefix_map=prefix_map,
            scan_root=scan_root,
            project_root=project_root,
        )
    except Exception as exc:  # noqa: BLE001 - fail-safe(F13) 최종 방어선
        return {
            "busy": False,
            "precondition_failed": False,
            "precondition": None,
            "unmapped": [],
            "dirty": [],
            "raw_name_conflicts": [],
            "raw_stage": _failed_raw_stage(f"unexpected error: {exc}"),
            "catalog_stage": _empty_catalog_stage(),
        }
