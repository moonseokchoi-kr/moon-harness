"""hooks/lib/kompound_snapshot/cli.py — F13 CLI 통합 (arch §6.2 "CLI 계약").

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md`
(이하 "arch") §6.2(CLI 서브커맨드·종료 코드·JSON 스키마 — 단일 진실),
§5.2.3(`gate` 5개 분기 제어 흐름·F9 선행 확인·T1→T2 승계 노출),
§5.1.3((i)/(ii) 정책), §4(의존 방향 — `cli` → 전 모듈).

## 이 모듈이 하는 일

`config → scan → naming → dedup → apply → registry/wiki_log(apply 내부)
→ verify(apply 내부) → git_state` 파이프라인을 3개 서브커맨드로 조립한다:

- **`check`** — read-only. 스캔·판정만 한다(부작용 없음). `pending`(exit 10)을
  반환할 수 있는 **유일한** 서브커맨드다.
- **`apply`** — 실제 박제 실행. `apply.apply()`를 호출한다(2단 raw/카탈로그
  커밋).
- **`gate`** — T2 bash 게이트가 호출. **exit 10을 반환하지 않는다** — 내부에서
  `apply`까지 수렴한다. F9 선행 확인 순서(arch §5.2.3)를 그대로 구현한다:
  `no_target → disabled → scan_error → unmapped_blocking → ok_no_pending →
  precondition_failed(F9) → apply 실행`. F9가 걸리면 `apply.apply()`는
  **호출조차 되지 않는다**(부작용 0).

종료 코드·verdict·JSON 스키마는 전부 `report.py`(T-6, 단일 진실)에서 가져다
쓴다 — 이 모듈은 그 표를 재정의하지 않는다.

## 이 모듈이 arch/task 위에서 직접 결정한 것 (§ "arch에 없어 직접 결정한 것" 참조)

각 결정의 근거는 함수 docstring에 있다. 요약:

1. **스코프 루트 기본값** — `--scope-root`/`--scope=workspace` 모두 생략하면
   `project_root` 1개를 스코프로 쓴다("repo 스코프", arch §2.3).
2. **`--scope=workspace`인데 `scan_root` 미해석** — 사용법 오류로 보고
   `errors[]`에 담아 `scan_error`로 귀결시킨다(F11 "조용한 실패 금지").
3. **`check`의 "미박제" 판정** — `apply.py`의 쓰기 로직(private)을 재사용하지
   않고, 동일한 F6 내용-비교 규칙을 **읽기 전용으로 재현**한다(`_dry_run_pending`)
   — `check`가 부작용 없이 "무엇이 pending인지"를 알아야 하기 때문이다.
4. **`anchors`/`config_source` JSON 필드 형태** — `report.build_report()`가
   `List[str]`로 타입힌트했으므로, `anchors`는 요약 문자열 1개짜리 리스트로,
   `config_source`는 `config["source"]` 전체를 JSON 문자열로 담는다(진단
   정보 보존, arch §6.1 "어디서 온 값인지 보여야 한다").
5. **F16 "안내 1회"는 `gate`에서만 소비한다** — M-18의 목적이 "매 Bash
   명령마다 떠드는 소음 방지"(PreToolUse)이므로, 반복 호출되는 `gate`만
   `runtime_state.should_emit_unconfigured_notice()`를 호출한다. `check`는
   이 함수가 상태 파일에 write하므로(부작용) 호출하지 않는다 — "check가
   부작용을 남기지 않는다"는 완료조건과 상충하기 때문이다. `apply`도 disabled
   경로에서는 아무 것도 안 하는 게 맞으므로 호출하지 않는다.
6. **`gate`의 승계 노출 "소비(clear)"** — `runtime_state.py`의 `status` 필드는
   T1(stop-pipeline.py, T-12)의 상태 머신이 소유하며, `gate`가 그 값을
   되돌리면 T1의 재블록 로직(§5.1.3 "GIVEN_UP passthrough")이 깨질 수 있다.
   그래서 `status`는 절대 건드리지 않고, 별도 마커 키
   `t2_inherited_consumed_status`(이 모듈 전용, T-7 스키마 밖)에 "이미
   보여준 status 값"만 기록해 반복 노출을 막는다.
7. **`gate`의 F9 선행 확인은 `apply.apply()` 호출 전에 별도로
   `git_state.check_preconditions()`를 직접 호출**한다 — task 완료조건이
   "F9가 걸리면 `apply`가 호출조차 되지 않음"을 명시적으로 요구하기 때문이다
   (`apply.apply()` 내부에도 동일 판정이 있지만, 그건 "apply를 호출한 뒤"의
   이야기라 이 요구를 충족하지 못한다).

## Fail-safe 규약 (F13)

`main()`이 최종 방어선이다 — 하위 모듈은 이미 예외를 던지지 않지만, 예상치
못한 예외가 발생해도 `main()`이 잡아 `scan_error`류 종료 코드로 귀결시킨다
(크래시 금지, 완료조건 12).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from hooks.lib.kompound_snapshot import config, git_state, naming, report, runtime_state, wt_target
from hooks.lib.self_improve.state_io import atomic_write, load_state

# scan/dedup/apply 모듈은 자기 이름과 똑같은 이름의 함수를 노출한다
# (`scan.scan`, `dedup.dedup`, `apply.apply`). `__init__.py`의 공개 API
# 재노출(`from .scan import scan` 등, self_improve/__init__.py 관례)이
# 실행되면서 패키지 속성 `hooks.lib.kompound_snapshot.scan`이 서브모듈에서
# **그 함수로 리바인딩**된다 — `import hooks.lib.kompound_snapshot.scan as x`
# 조차 (CPython이 dotted import의 `as` 바인딩을 속성 체인으로 해석하므로)
# 이 리바인딩된 함수를 그대로 가져온다(패키지 attribute shadowing, 실측
# 확인됨). 이 세 모듈만 `importlib.import_module()`로 `sys.modules`에서
# 직접 꺼낸다 — 이 경로는 패키지 속성 리바인딩과 무관하게 항상 진짜
# 서브모듈 객체를 반환한다.
scan = importlib.import_module("hooks.lib.kompound_snapshot.scan")
dedup = importlib.import_module("hooks.lib.kompound_snapshot.dedup")
apply_mod = importlib.import_module("hooks.lib.kompound_snapshot.apply")

__all__ = ["build_parser", "main"]

PathLike = Union[str, Path]

_ENV_CLAUDE_PROJECT_DIR = "CLAUDE_PROJECT_DIR"

# gate가 T1→T2 승계 노출을 "소비(clear)"했음을 표시하는 이 모듈 전용 마커
# 키 — runtime_state.py(T-7)의 6종 스키마에 속하지 않는다(설계 결정 6 참조).
_INHERITED_CONSUMED_KEY = "t2_inherited_consumed_status"


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────


def _default_project_root() -> Path:
    """`config.py`/`runtime_state.py`와 동일한 기본 project_root 규약.

    `CLAUDE_PROJECT_DIR` 환경변수 우선, 없으면 `os.getcwd()` — 이 레포
    어댑터들의 기존 관례(`stop-pipeline.py`)와 동일하다. `config.py`의
    `_default_project_root()`는 private이라 재사용할 수 없으므로 동일 규약을
    이 모듈에도 둔다(1줄짜리 env 조회 — "핵심 판정 로직"이 아니라 중복
    허용 범위로 판단했다).
    """
    return Path(os.environ.get(_ENV_CLAUDE_PROJECT_DIR, os.getcwd()))


def _config_source_str(cfg: Optional[Mapping[str, Any]]) -> str:
    """`config["source"]`(env|project|home|discovery 맵) 전체를 JSON 문자열로
    담는다 — `config_source`가 단일 `str` 필드라서(arch §6.2 JSON 스키마),
    필드별 출처를 보존하려면 직렬화가 필요하다(arch §6.1 "어디서 온 값인지
    보여야 한다")."""
    if not cfg:
        return ""
    try:
        return json.dumps(cfg.get("source", {}), sort_keys=True, ensure_ascii=False)
    except Exception:  # noqa: BLE001 - fail-safe, 진단 문자열 조립 실패는 무시
        return ""


def _format_anchors(anchor_count: Optional[int], max_anchor_depth: int) -> List[str]:
    """`report.build_report()`가 `anchors`를 `List[str]`로 기대하므로(설계
    결정 4), "N anchors (depth_limit=D)" 요약 문자열 1개짜리 리스트로 담는다.
    스캔을 하지 않은 경로(예: disabled)는 `anchor_count=None`으로 빈 리스트."""
    if anchor_count is None:
        return []
    return [f"{anchor_count} anchors (depth_limit={max_anchor_depth})"]


def _format_errors(errors: Sequence[Any]) -> List[str]:
    out: List[str] = []
    for e in errors:
        if isinstance(e, dict):
            out.append(f"{e.get('path', '')}: {e.get('error', '')}")
        else:
            out.append(str(e))
    return out


def _read_runtime_status(project_root: PathLike) -> Tuple[str, int]:
    """읽기 전용으로 현재 런타임 상태(`status`/`catalog_lag_count`)를 조회한다.

    파일이 없거나 값이 6종 밖이면 ``("SKIPPED_UNCONFIGURED", 0)``으로
    안전하게 폴백한다 — 이 CLI는 `runtime_state.py`가 이미 기록한 값을
    반영만 할 뿐 새 상태를 발명하지 않는다(단일 진실 = `runtime_state.py`).
    """
    try:
        state_file = runtime_state.state_path_for(project_root)
        data = load_state(state_file)
        if not isinstance(data, dict):
            return runtime_state.SKIPPED_UNCONFIGURED, 0
        status = data.get("status")
        if status not in runtime_state.STATUSES:
            return runtime_state.SKIPPED_UNCONFIGURED, 0
        lag = int(data.get("catalog_lag_count", 0) or 0)
        return str(status), lag
    except Exception:  # noqa: BLE001 - fail-safe
        return runtime_state.SKIPPED_UNCONFIGURED, 0


def _consume_inherited_warning(project_root: PathLike) -> Dict[str, Any]:
    """`gate` 전용 — 판정 **전에** T1 실패/카탈로그 지연 승계를 소비한다
    (arch §5.2.3, task 완료조건). `FAILED`/`GIVEN_UP`(실패 톤)·
    `CATALOG_PENDING`(정보 톤)만 승계 대상이고, 그 외(`DONE`/`PENDING`/
    `SKIPPED_UNCONFIGURED`)는 승계하지 않는다.

    같은 `status` 값에 대해 한 번만 노출한다 — `runtime_state.py`의 `status`
    필드 자체는 절대 되돌리지 않고(T1의 재블록 로직을 깨뜨릴 위험, 설계
    결정 6), 이 모듈 전용 마커 키(`_INHERITED_CONSUMED_KEY`)에 "마지막으로
    보여준 status"만 기록한다.
    """
    try:
        state_file = runtime_state.state_path_for(project_root)
        data = load_state(state_file)
        if not isinstance(data, dict):
            return {"kind": None, "text": ""}

        status = data.get("status")
        if status not in (
            runtime_state.FAILED,
            runtime_state.GIVEN_UP,
            runtime_state.CATALOG_PENDING,
        ):
            return {"kind": None, "text": ""}

        if data.get(_INHERITED_CONSUMED_KEY) == status:
            return {"kind": None, "text": ""}  # 이미 이 값으로 노출했음 — 반복 억제

        lag = int(data.get("catalog_lag_count", 0) or 0)
        if status == runtime_state.GIVEN_UP:
            # 최초 연산자 우선순위 실수를 피하려고 분기를 명시적으로 나눈다
            # (`A or B if C else D`는 `(A or B) if C else D`로 파싱돼
            # FAILED 분기의 `data.get("error")`를 조용히 버렸었다).
            reason = str(data.get("error") or "budget_exhausted")
        elif status == runtime_state.FAILED:
            reason = str(data.get("error") or "")
        else:
            reason = ""
        warning = report.build_inherited_warning(status, reason=reason, catalog_lag_count=lag)

        updated = dict(data)
        updated[_INHERITED_CONSUMED_KEY] = status
        atomic_write(state_file, updated)
        return warning
    except Exception:  # noqa: BLE001 - fail-safe, 승계 노출 실패는 조용히 무시(경고 없음보다 크래시가 더 나쁘다)
        return {"kind": None, "text": ""}


def _resolve_scope_roots(
    scope_roots_arg: Optional[Sequence[str]],
    scope_arg: Optional[str],
    cfg: Mapping[str, Any],
    project_root: Path,
) -> Tuple[List[Path], List[Dict[str, str]]]:
    """`--scope-root`(반복)/`--scope=workspace`/기본값(설계 결정 1) 순으로
    스코프 루트를 정한다.

    - `--scope-root`가 하나 이상 주어지면 그 목록을 그대로 쓴다.
    - 그렇지 않고 `--scope=workspace`면 `config["scan_root"]` 1개를 쓴다.
      `scan_root`가 미해석이면(설계 결정 2) 사용법 오류로 보고
      `errors[]`에 담아 반환한다(스캔은 시도하지 않는다).
    - 둘 다 없으면 `project_root` 1개("repo 스코프").
    """
    errors: List[Dict[str, str]] = []
    if scope_roots_arg:
        return [Path(p) for p in scope_roots_arg], errors

    if scope_arg == "workspace":
        scan_root = cfg.get("scan_root")
        if not scan_root:
            errors.append(
                {
                    "path": "",
                    "error": "scan_root not configured (F16); --scope=workspace unusable",
                }
            )
            return [], errors
        return [Path(scan_root)], errors

    return [project_root], errors


def _dry_run_pending(
    canonical_records: Sequence[Mapping[str, Any]],
    prefix_map: Mapping[str, Optional[str]],
    scan_root: Optional[str],
    kompound_repo: Optional[str],
) -> Tuple[List[str], List[str]]:
    """`check`/`gate`의 읽기 전용 "미박제 판정"(설계 결정 3).

    `apply.py`가 실제로 쓸 때 쓰는 F6 규칙(없으면 신규, 같으면 무동작, 다르면
    갱신)과 동일한 내용 비교를 **파일을 쓰지 않고** 재현한다. `apply.py`의
    `_prepare_raw_writes`/`_write_raw_files`는 private(밑줄 접두)이라 다른
    모듈이 재사용할 수 없으므로, 이 모듈이 동일 규칙을 읽기 전용으로
    재구현한다 — 이것이 "check는 부작용 없음"과 "apply는 실제 실행"을 서로
    다른 코드 경로로 만드는 유일한 방법이다.

    반환: ``(pending_basenames, unmapped_repo_dirs)``. `kompound_repo`가
    미해석이면(호출자가 이미 `disabled`로 처리했어야 하지만, 방어적으로)
    빈 두 리스트를 반환한다.
    """
    pending: List[str] = []
    unmapped: List[str] = []
    if not kompound_repo:
        return pending, unmapped

    raw_root = Path(kompound_repo) / "raw"
    for record in canonical_records:
        naming_result = naming.name_document(record, prefix_map, scan_root)
        if "unmapped" in naming_result:
            unmapped.append(str(naming_result["unmapped"]))
            continue

        basename = Path(naming_result["raw_name"]).name
        target = raw_root / basename
        try:
            if not target.is_file():
                pending.append(basename)
                continue
            source_bytes = Path(record["path"]).read_bytes()
            if target.read_bytes() != source_bytes:
                pending.append(basename)
        except OSError:
            # 읽기 실패(권한 등) — fail-safe: "확인 못 함"을 "이미 됐음"으로
            # 조용히 넘기지 않고 보수적으로 pending 쪽에 둔다(F11 정신).
            pending.append(basename)

    return pending, unmapped


def _map_apply_result_to_verdict(result: Mapping[str, Any]) -> Tuple[str, str]:
    """`apply.apply()`의 2단 결과를 verdict로 매핑한다(arch §6.2 "apply 2단
    결과 → verdict 매핑" 표). 반환: ``(verdict, detail)``."""
    if result.get("busy"):
        return "busy", ""

    if result.get("precondition_failed"):
        precondition = result.get("precondition") or {}
        return "precondition_failed", str(precondition.get("reason") or "")

    raw_stage = result["raw_stage"]
    catalog_stage = result["catalog_stage"]

    if not raw_stage.get("ok"):
        return "write_failed", str(raw_stage.get("error", ""))

    if catalog_stage.get("attempted") and not catalog_stage.get("ok"):
        failed_gates = catalog_stage.get("failed_gates") or []
        if failed_gates:
            return "verify_failed", "; ".join(failed_gates)
        return "catalog_unparsed", str(catalog_stage.get("unparsed") or catalog_stage.get("error") or "")

    changed = bool(raw_stage.get("new")) or bool(raw_stage.get("updated"))
    catalog_committed = bool(catalog_stage.get("committed"))
    if changed or catalog_committed:
        return "snapshotted", ""
    return "ok_no_pending", ""


def _finalize_report(
    verdict: str,
    project_root: PathLike,
    *,
    cfg: Optional[Mapping[str, Any]] = None,
    scope_roots: Sequence[Any] = (),
    anchor_count: Optional[int] = None,
    max_anchor_depth: int = 5,
    raw_stage: Optional[Dict[str, Any]] = None,
    catalog_stage: Optional[Dict[str, Any]] = None,
    unmapped: Sequence[str] = (),
    pending: Sequence[str] = (),
    dirty: Sequence[str] = (),
    errors: Sequence[Any] = (),
    inherited_warning: Optional[Dict[str, Any]] = None,
    detail: str = "",
) -> Dict[str, Any]:
    """모든 서브커맨드가 공유하는 리포트 조립 지점 — `report.build_report()`에
    위임하고, 이 모듈이 계산한 필드(runtime_status/catalog_lag_count/anchors/
    config_source 등)만 채운다. verdict/exit_code/blocks_deletion 판정 로직
    자체는 재구현하지 않는다(단일 진실은 `report.py`)."""
    runtime_status, catalog_lag = _read_runtime_status(project_root)
    return report.build_report(
        verdict=verdict,
        config_source=_config_source_str(cfg),
        scope_roots=[str(p) for p in scope_roots],
        anchors=_format_anchors(anchor_count, max_anchor_depth),
        raw_stage=raw_stage,
        catalog_stage=catalog_stage,
        unmapped=list(unmapped),
        pending=list(pending),
        dirty=list(dirty),
        errors=_format_errors(errors),
        runtime_status=runtime_status,
        catalog_lag_count=catalog_lag,
        inherited_warning=inherited_warning,
        detail=detail,
    )


# ── argparse (arch §6.2 "호출 형태") ────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """3개 서브커맨드(`check`/`apply`/`gate`)를 정의한다.

    서브프로세스 없이도 단위 테스트 가능(`evals/run_eval.py` 관례) —
    `main(argv)`가 이 파서로 argv를 직접 파싱한다. 하위호환용 `--check`
    별칭은 두지 않는다(task 완료조건, 노브 최소화).
    """
    parser = argparse.ArgumentParser(
        prog="kompound_snapshot",
        description="kompound SDD 스냅샷 코어 CLI (check/apply/gate)",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    check_parser = subparsers.add_parser(
        "check", help="read-only pending 스캔 — 부작용 없음"
    )
    check_parser.add_argument(
        "--scope-root", action="append", dest="scope_roots", metavar="PATH",
        help="스캔 스코프 루트(반복 가능). 생략하면 project_root 1개",
    )
    check_parser.add_argument(
        "--scope", choices=["workspace"], default=None,
        help="scope=workspace면 config의 scan_root를 스코프로 쓴다",
    )
    check_parser.add_argument("--json", action="store_true", default=False)

    apply_parser = subparsers.add_parser(
        "apply", help="박제 실행 — (i) raw 커밋 → (ii) 카탈로그 커밋"
    )
    apply_parser.add_argument(
        "--scope-root", action="append", dest="scope_roots", metavar="PATH"
    )
    apply_parser.add_argument("--scope", choices=["workspace"], default=None)
    apply_parser.add_argument("--json", action="store_true", default=False)

    gate_parser = subparsers.add_parser(
        "gate", help="T2 PreToolUse 게이트가 호출 — exit 10을 반환하지 않는다"
    )
    gate_parser.add_argument("--command", required=True, help="원본 Bash 명령 문자열")
    gate_parser.add_argument("--json", action="store_true", default=False)

    return parser


# ── 서브커맨드 구현 ──────────────────────────────────────────────────────────


def _cmd_check(args: argparse.Namespace) -> int:
    project_root = _default_project_root()
    json_mode = bool(args.json)

    cfg = config.resolve_config(project_root)
    if not cfg["ok"]:
        rep = _finalize_report("disabled", project_root, cfg=cfg)
        return report.emit_report(rep, json_mode=json_mode)

    scope_roots, scope_errors = _resolve_scope_roots(
        getattr(args, "scope_roots", None), getattr(args, "scope", None), cfg, project_root
    )
    scan_result = scan.scan(scope_roots, max_anchor_depth=cfg["max_anchor_depth"])
    all_errors = list(scan_result["errors"]) + scope_errors
    if all_errors:
        rep = _finalize_report(
            "scan_error", project_root, cfg=cfg,
            scope_roots=scope_roots, anchor_count=scan_result["anchors"],
            max_anchor_depth=cfg["max_anchor_depth"], errors=all_errors,
            detail="; ".join(_format_errors(all_errors)),
        )
        return report.emit_report(rep, json_mode=json_mode)

    canonical = dedup.dedup(scan_result["records"])
    pending, unmapped = _dry_run_pending(canonical, cfg["prefix_map"], cfg["scan_root"], cfg["kompound_repo"])
    verdict = "pending" if pending else "ok_no_pending"

    rep = _finalize_report(
        verdict, project_root, cfg=cfg,
        scope_roots=scope_roots, anchor_count=scan_result["anchors"],
        max_anchor_depth=cfg["max_anchor_depth"], unmapped=unmapped, pending=pending,
    )
    return report.emit_report(rep, json_mode=json_mode)


def _cmd_apply(args: argparse.Namespace) -> int:
    project_root = _default_project_root()
    json_mode = bool(args.json)

    cfg = config.resolve_config(project_root)
    if not cfg["ok"]:
        rep = _finalize_report("disabled", project_root, cfg=cfg)
        return report.emit_report(rep, json_mode=json_mode)

    scope_roots, scope_errors = _resolve_scope_roots(
        getattr(args, "scope_roots", None), getattr(args, "scope", None), cfg, project_root
    )
    scan_result = scan.scan(scope_roots, max_anchor_depth=cfg["max_anchor_depth"])
    all_errors = list(scan_result["errors"]) + scope_errors
    if all_errors:
        rep = _finalize_report(
            "scan_error", project_root, cfg=cfg,
            scope_roots=scope_roots, anchor_count=scan_result["anchors"],
            max_anchor_depth=cfg["max_anchor_depth"], errors=all_errors,
            detail="; ".join(_format_errors(all_errors)),
        )
        return report.emit_report(rep, json_mode=json_mode)

    canonical = dedup.dedup(scan_result["records"])
    apply_result = apply_mod.apply(
        cfg["kompound_repo"], canonical,
        prefix_map=cfg["prefix_map"], scan_root=cfg["scan_root"], project_root=project_root,
    )
    verdict, detail = _map_apply_result_to_verdict(apply_result)

    rep = _finalize_report(
        verdict, project_root, cfg=cfg,
        scope_roots=scope_roots, anchor_count=scan_result["anchors"],
        max_anchor_depth=cfg["max_anchor_depth"],
        raw_stage=apply_result["raw_stage"], catalog_stage=apply_result["catalog_stage"],
        unmapped=apply_result.get("unmapped", []), dirty=apply_result.get("dirty", []),
        detail=detail,
    )
    return report.emit_report(rep, json_mode=json_mode)


def _cmd_gate(args: argparse.Namespace) -> int:
    """arch §5.2.3 5개 분기 + F9 선행 확인 순서를 그대로 구현한다:
    `no_target → disabled → scan_error → unmapped_blocking → ok_no_pending →
    precondition_failed(F9) → apply 실행`. `apply.apply()`는 F9가 걸리지
    않았을 때만(즉 위 5개 조기 반환을 전부 통과했을 때만) 호출된다."""
    project_root = _default_project_root()
    json_mode = bool(args.json)

    # 판정 전에 T1 승계 노출을 먼저 소비한다(arch §5.2.3) — 이후 verdict가
    # 무엇이 되든 이 값을 그대로 리포트에 담는다.
    inherited = _consume_inherited_warning(project_root)

    targets = wt_target.find_worktree_removal_targets(args.command or "")
    if not targets:
        rep = _finalize_report("no_target", project_root, inherited_warning=inherited)
        return report.emit_report(rep, json_mode=json_mode)

    cfg = config.resolve_config(project_root)
    if not cfg["ok"]:
        notify = runtime_state.should_emit_unconfigured_notice(project_root)
        rep = _finalize_report(
            "disabled", project_root, cfg=cfg, scope_roots=targets, inherited_warning=inherited
        )
        if not notify:
            rep["human"] = ""  # M-18 "안내 1회" — 같은 세션/24h 창 안에서는 반복 노출하지 않는다
        return report.emit_report(rep, json_mode=json_mode)

    scan_result = scan.scan(targets, max_anchor_depth=cfg["max_anchor_depth"])
    if scan_result["errors"]:
        rep = _finalize_report(
            "scan_error", project_root, cfg=cfg,
            scope_roots=targets, anchor_count=scan_result["anchors"],
            max_anchor_depth=cfg["max_anchor_depth"], errors=scan_result["errors"],
            detail="; ".join(_format_errors(scan_result["errors"])),
            inherited_warning=inherited,
        )
        return report.emit_report(rep, json_mode=json_mode)

    canonical = dedup.dedup(scan_result["records"])
    pending, unmapped = _dry_run_pending(canonical, cfg["prefix_map"], cfg["scan_root"], cfg["kompound_repo"])

    if unmapped:
        rep = _finalize_report(
            "unmapped_blocking", project_root, cfg=cfg,
            scope_roots=targets, anchor_count=scan_result["anchors"],
            max_anchor_depth=cfg["max_anchor_depth"], unmapped=unmapped, pending=pending,
            detail=", ".join(unmapped[:5]),
            inherited_warning=inherited,
        )
        return report.emit_report(rep, json_mode=json_mode)

    if not pending:
        rep = _finalize_report(
            "ok_no_pending", project_root, cfg=cfg,
            scope_roots=targets, anchor_count=scan_result["anchors"],
            max_anchor_depth=cfg["max_anchor_depth"], unmapped=unmapped, pending=pending,
            inherited_warning=inherited,
        )
        return report.emit_report(rep, json_mode=json_mode)

    # F9 선행 확인 — apply.apply()를 호출하기 전에 직접 판정한다(설계 결정 7).
    # 여기서 걸리면 apply.apply()는 이 함수 안에서 단 한 번도 호출되지 않는다.
    precondition = git_state.check_preconditions(cfg["kompound_repo"])
    if precondition["precondition_failed"]:
        rep = _finalize_report(
            "precondition_failed", project_root, cfg=cfg,
            scope_roots=targets, anchor_count=scan_result["anchors"],
            max_anchor_depth=cfg["max_anchor_depth"], unmapped=unmapped, pending=pending,
            dirty=precondition.get("dirty_files", []),
            detail=str(precondition.get("reason") or ""),
            inherited_warning=inherited,
        )
        return report.emit_report(rep, json_mode=json_mode)

    apply_result = apply_mod.apply(
        cfg["kompound_repo"], canonical,
        prefix_map=cfg["prefix_map"], scan_root=cfg["scan_root"], project_root=project_root,
    )
    verdict, detail = _map_apply_result_to_verdict(apply_result)

    rep = _finalize_report(
        verdict, project_root, cfg=cfg,
        scope_roots=targets, anchor_count=scan_result["anchors"],
        max_anchor_depth=cfg["max_anchor_depth"], unmapped=unmapped, pending=pending,
        raw_stage=apply_result["raw_stage"], catalog_stage=apply_result["catalog_stage"],
        dirty=apply_result.get("dirty", []),
        detail=detail,
        inherited_warning=inherited,
    )
    return report.emit_report(rep, json_mode=json_mode)


# ── 엔트리포인트 ─────────────────────────────────────────────────────────────


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI 최상위 진입점. `SystemExit`(argparse의 `--help`/사용법 오류)은
    그대로 전파하고(표준 CLI 관례), 그 외 예상치 못한 예외는 전부 이
    함수가 잡아 `scan_error`류 종료 코드로 변환한다(F13 fail-safe 최종
    방어선, 완료조건 12) — 크래시하지 않는다."""
    try:
        parser = build_parser()
        args = parser.parse_args(argv)

        if args.subcommand == "check":
            return _cmd_check(args)
        if args.subcommand == "apply":
            return _cmd_apply(args)
        if args.subcommand == "gate":
            return _cmd_gate(args)
        return report.EXIT_SCAN_ERROR  # 이론상 도달 불가(argparse required=True)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - F13 fail-safe 최종 방어선
        try:
            sys.stderr.write(f"[kompound-snapshot] unexpected error: {exc}\n")
        except Exception:  # noqa: BLE001 - 출력 실패도 크래시로 이어지지 않게
            pass
        return report.EXIT_SCAN_ERROR
