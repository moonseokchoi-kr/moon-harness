"""hooks.lib.kompound_snapshot.report — F11 verdict/종료 코드/리포트 (arch §6.2).

이 모듈이 **종료 코드 표(0/10/20/30/40/45/50/55/60/70)의 단일 진실**이다
(T-2 확정 사항 #1). ``__init__.py``·``runtime_state``를 포함한 다른 모든
모듈·어댑터(T1 `stop-pipeline.py`, T2 `kompound-snapshot-gate.sh`, T-10
`apply.py`, T-11 `cli.py`, T-13 게이트 스크립트)는 이 표의 값을 재정의하지
않고 여기서 가져다 쓴다.

## 핵심 계약 — "단계"가 T2 정책을 결정한다 (arch A-5)

각 verdict는 **어느 단계의 실패인지**(``stage``)와 **그 실패가 삭제를
차단해야 하는지**(``blocks_deletion``)를 함께 갖는다:

- ``stage="raw"`` — (i) raw 복사 단계. 실패하면 문서가 kompound에 없다 →
  **차단**.
- ``stage="catalog"`` — (ii) 카탈로그(registry/index/log) 갱신 단계. raw는
  이미 커밋됐으므로 실패해도 문서 소실 위험이 없다 → **경고 후 통과**.
- ``stage in {"scan","precondition","lock"}`` — (i) 이전 단계. "판정 자체를
  못 했거나(scan) 안전을 확신할 수 없다(precondition/lock)"는 뜻이라 보수적
  으로 **차단**한다.
- ``stage="none"`` — 정상/비활성 종료(변경 없음, 완료, 비활성화 등). 차단
  아님.

T-10(`apply.py`)·T-11(`cli.py`)·T-13(bash 게이트)은 이 표를 통해 exit_code ↔
stage ↔ blocks_deletion을 조회하기만 하면 되고, 축 판정(arch §5.2.4)을
재구현하지 않는다.

## Fail-safe 규약

모든 공개 함수는 예외를 던지지 않는다. 알 수 없는 verdict는 보수적으로
"차단"(scan_error에 준하는 취급)으로 흡수한다 — F11 "조용한 0건 금지"의
정신과 같다: 모르면 안전 쪽(차단/경고)으로 넘어간다.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, TextIO

__all__ = [
    "EXIT_OK",
    "EXIT_PENDING",
    "EXIT_DISABLED",
    "EXIT_SCAN_ERROR",
    "EXIT_PRECONDITION_FAILED",
    "EXIT_UNMAPPED_BLOCKING",
    "EXIT_VERIFY_FAILED",
    "EXIT_CATALOG_UNPARSED",
    "EXIT_WRITE_FAILED",
    "EXIT_BUSY",
    "STAGE_NONE",
    "STAGE_SCAN",
    "STAGE_PRECONDITION",
    "STAGE_LOCK",
    "STAGE_RAW",
    "STAGE_CATALOG",
    "VERDICT_TABLE",
    "RUNTIME_STATUSES",
    "exit_code_for_verdict",
    "stage_for_verdict",
    "blocks_deletion",
    "pending_unmapped_disjoint",
    "build_inherited_warning",
    "build_human_text",
    "build_report",
    "emit_report",
]

# ── 종료 코드 (arch §6.2 — 단일 진실. 1·2는 예약, 사용하지 않는다) ──────

EXIT_OK = 0
EXIT_PENDING = 10
EXIT_DISABLED = 20
EXIT_SCAN_ERROR = 30
EXIT_PRECONDITION_FAILED = 40
EXIT_UNMAPPED_BLOCKING = 45
EXIT_VERIFY_FAILED = 50
EXIT_CATALOG_UNPARSED = 55
EXIT_WRITE_FAILED = 60
EXIT_BUSY = 70

# ── 단계 라벨 (arch §6.2 "단계" 열 + A-5 축 판정) ──────────────────────

STAGE_NONE = "none"
STAGE_SCAN = "scan"
STAGE_PRECONDITION = "precondition"
STAGE_LOCK = "lock"
STAGE_RAW = "raw"  # (i)
STAGE_CATALOG = "catalog"  # (ii)

# runtime_state의 상태 값 6종 (단일 진실은 runtime_state.py, arch §5.1.2) —
# 여기서는 JSON 스키마 검증/참조용으로만 나열한다(재정의 아님, T-2 확정 사항 #1).
RUNTIME_STATUSES = (
    "PENDING",
    "CATALOG_PENDING",
    "DONE",
    "SKIPPED_UNCONFIGURED",
    "FAILED",
    "GIVEN_UP",
)

# verdict ↔ (exit_code, stage, blocks_deletion) — arch §6.2 표 + §5.2.4 3축.
VERDICT_TABLE: Dict[str, Dict[str, Any]] = {
    "ok_no_pending": {"exit_code": EXIT_OK, "stage": STAGE_NONE, "blocks_deletion": False},
    "snapshotted": {"exit_code": EXIT_OK, "stage": STAGE_NONE, "blocks_deletion": False},
    "no_target": {"exit_code": EXIT_OK, "stage": STAGE_NONE, "blocks_deletion": False},
    "pending": {"exit_code": EXIT_PENDING, "stage": STAGE_NONE, "blocks_deletion": False},
    "disabled": {"exit_code": EXIT_DISABLED, "stage": STAGE_NONE, "blocks_deletion": False},
    "scan_error": {"exit_code": EXIT_SCAN_ERROR, "stage": STAGE_SCAN, "blocks_deletion": True},
    "precondition_failed": {
        "exit_code": EXIT_PRECONDITION_FAILED,
        "stage": STAGE_PRECONDITION,
        "blocks_deletion": True,
    },
    "unmapped_blocking": {
        "exit_code": EXIT_UNMAPPED_BLOCKING,
        "stage": STAGE_PRECONDITION,
        "blocks_deletion": True,
    },
    "verify_failed": {
        "exit_code": EXIT_VERIFY_FAILED,
        "stage": STAGE_CATALOG,
        "blocks_deletion": False,
    },
    "catalog_unparsed": {
        "exit_code": EXIT_CATALOG_UNPARSED,
        "stage": STAGE_CATALOG,
        "blocks_deletion": False,
    },
    "write_failed": {"exit_code": EXIT_WRITE_FAILED, "stage": STAGE_RAW, "blocks_deletion": True},
    "busy": {"exit_code": EXIT_BUSY, "stage": STAGE_LOCK, "blocks_deletion": True},
}

# 알 수 없는 verdict의 안전한 폴백 — 조용히 통과시키지 않는다(F11 정신).
_UNKNOWN_VERDICT_FALLBACK = {
    "exit_code": EXIT_SCAN_ERROR,
    "stage": STAGE_SCAN,
    "blocks_deletion": True,
}


def _lookup(verdict: str) -> Dict[str, Any]:
    if not isinstance(verdict, str):
        return _UNKNOWN_VERDICT_FALLBACK
    return VERDICT_TABLE.get(verdict, _UNKNOWN_VERDICT_FALLBACK)


def exit_code_for_verdict(verdict: str) -> int:
    """`verdict` 문자열에 대응하는 종료 코드(arch §6.2 표)를 반환한다.

    알 수 없는 verdict는 30(``scan_error``)으로 안전하게 폴백한다(절대
    조용히 0을 반환하지 않는다 — F11).
    """
    return int(_lookup(verdict)["exit_code"])


def stage_for_verdict(verdict: str) -> str:
    """`verdict`가 어느 단계의 실패/성공인지(raw/(i) vs catalog/(ii) vs
    scan/precondition/lock vs none)를 반환한다."""
    return str(_lookup(verdict)["stage"])


def blocks_deletion(verdict: str) -> bool:
    """이 `verdict`가 T2(워크트리 삭제)를 차단해야 하는지(arch §5.2.4 3축)."""
    return bool(_lookup(verdict)["blocks_deletion"])


def pending_unmapped_disjoint(pending: List[str], unmapped: List[str]) -> bool:
    """`pending`과 `unmapped`가 서로 배타적 집합인지(F12/§5.1.3 J-11)를
    확인하는 순수 헬퍼. 두 리스트에 동시에 등장하는 원소가 있으면 False.
    비교 불가능한 입력은 보수적으로 True(문제 없음으로 취급)를 반환한다.
    """
    try:
        return not (set(pending) & set(unmapped))
    except TypeError:
        return True


# ── inherited_warning 조립 (arch §5.2.3 T1→T2 승계 노출) ───────────────


def build_inherited_warning(
    runtime_status: str,
    *,
    reason: str = "",
    catalog_lag_count: int = 0,
) -> Dict[str, Any]:
    """`runtime_status`(T1 런타임 상태)로부터 T2에 승계할 경고 객체를 만든다.

    항상 ``{"kind": "failure"|"info"|None, "text": str}`` **객체**를
    반환한다(문자열이 아니다 — arch §6.2). 승계 대상이 아니면
    ``{"kind": None, "text": ""}``.

    - ``FAILED``/``GIVEN_UP`` → ``kind="failure"`` (T1 박제 실패 — 문서가
      보존되지 않았을 수 있음).
    - ``CATALOG_PENDING`` → ``kind="info"`` (raw는 보존·커밋됐고 카탈로그만
      뒤처짐 — 삭제는 안전함).
    - 그 외(``DONE``/``PENDING``/``SKIPPED_UNCONFIGURED``/알 수 없는 값)
      → 승계 안 함.
    """
    try:
        if runtime_status in ("FAILED", "GIVEN_UP"):
            suffix = f"({reason})" if reason else ""
            text = f"T1 박제가 실패했습니다{suffix}. 문서가 보존되지 않았을 수 있습니다."
            return {"kind": "failure", "text": text}

        if runtime_status == "CATALOG_PENDING":
            text = (
                f"raw는 보존·커밋됐고 카탈로그가 뒤처져 있습니다"
                f"({catalog_lag_count} 사이클). 삭제는 안전합니다."
            )
            return {"kind": "info", "text": text}

        return {"kind": None, "text": ""}
    except Exception:  # noqa: BLE001 - fail-safe
        return {"kind": None, "text": ""}


# ── human 텍스트 조립 (arch §5.2.4 — 차단은 3요소, 축3 통과는 보존/잔여) ──

_BLOCK_REASON_TEXT = {
    "scan_error": "kompound 문서 스캔 중 오류가 발생해 어떤 문서가 있는지 확인하지 못했습니다",
    "precondition_failed": "kompound 저장소가 dirty이거나 upstream과 어긋나 있습니다",
    "unmapped_blocking": "삭제 대상 안에 프리픽스가 등록되지 않은 문서가 있어 박제할 수 없습니다",
    "write_failed": "raw 문서를 kompound에 복사·커밋하지 못했습니다",
    "busy": "다른 프로세스가 kompound 락을 잡고 있습니다",
}

_PASS_TEXT = {
    "ok_no_pending": "[kompound-snapshot] 박제할 문서가 없습니다(변경 없음).",
    "snapshotted": "[kompound-snapshot] 문서를 박제했습니다.",
    "no_target": "[kompound-snapshot] 이 명령은 워크트리 삭제 대상이 아닙니다.",
    "pending": "[kompound-snapshot] 박제 대기 중인 문서가 있습니다.",
    "disabled": "[kompound-snapshot] kompound 경로가 설정되지 않아 기능이 비활성화되어 있습니다.",
}


def _default_raw_stage() -> Dict[str, Any]:
    return {
        "ok": True,
        "new": [],
        "updated": [],
        "unchanged": 0,
        "committed": False,
        "commit": None,
        "error": "",
    }


def _default_catalog_stage() -> Dict[str, Any]:
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


def build_human_text(
    verdict: str,
    *,
    raw_stage: Optional[Dict[str, Any]] = None,
    catalog_stage: Optional[Dict[str, Any]] = None,
    detail: str = "",
) -> str:
    """사람이 읽는 리포트 텍스트를 조립한다.

    - **차단 케이스**(``blocks_deletion(verdict) is True``): 항상 3요소를
      포함한다 — 무엇이 왜 막혔는가 / 수동 절차 / 끄는 방법
      (``HARNESS_KOMPOUND_REPO`` 비우기).
    - **축 3 통과 케이스**(``stage == "catalog"``, 즉 ``verify_failed``/
      ``catalog_unparsed``): 무엇이 보존됐고 무엇이 남았는지를 명시한다 —
      "raw N건 복사·커밋 완료 / 카탈로그 갱신 실패(사유) → 다음 실행에서
      재시도".
    - 그 외 통과 케이스: 짧은 상태 안내.
    """
    try:
        raw_stage = raw_stage if raw_stage is not None else _default_raw_stage()
        catalog_stage = catalog_stage if catalog_stage is not None else _default_catalog_stage()
        stage = stage_for_verdict(verdict)

        if blocks_deletion(verdict):
            reason = detail or _BLOCK_REASON_TEXT.get(verdict, f"{verdict} 상태입니다")
            return (
                f"[kompound-snapshot] 워크트리 삭제를 차단했습니다 — {reason}.\n"
                "수동 절차: SDD 산출물(spec/arch/ui/api/result 등)을 marvelous_kompound의 "
                "raw/에 verbatim 복사하고 registry/index.md/log.md를 직접 갱신한 뒤 "
                "다시 시도하세요.\n"
                "이 기능이 필요 없다면 HARNESS_KOMPOUND_REPO 환경변수를 비워서 끌 수 "
                "있습니다."
            )

        if stage == STAGE_CATALOG:
            new_n = len(raw_stage.get("new") or [])
            updated_n = len(raw_stage.get("updated") or [])
            reason = (
                detail
                or catalog_stage.get("error")
                or catalog_stage.get("unparsed")
                or "카탈로그 형상을 인식하지 못함"
            )
            return (
                f"raw {new_n + updated_n}건 복사·커밋 완료 / 카탈로그 갱신 실패"
                f"({reason}) → 다음 실행에서 재시도합니다. 삭제는 안전합니다."
            )

        return _PASS_TEXT.get(verdict, f"[kompound-snapshot] 통과 ({verdict}).")
    except Exception as exc:  # noqa: BLE001 - fail-safe
        return f"[kompound-snapshot] human 텍스트 조립 중 오류: {exc}"


# ── JSON 리포트 조립 (arch §6.2 스키마) ────────────────────────────────


def build_report(
    *,
    verdict: str,
    config_source: str = "",
    scope_roots: Optional[List[str]] = None,
    anchors: Optional[List[str]] = None,
    raw_stage: Optional[Dict[str, Any]] = None,
    catalog_stage: Optional[Dict[str, Any]] = None,
    unmapped: Optional[List[str]] = None,
    pending: Optional[List[str]] = None,
    dirty: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
    runtime_status: str = "SKIPPED_UNCONFIGURED",
    catalog_lag_count: int = 0,
    inherited_warning: Optional[Dict[str, Any]] = None,
    detail: str = "",
) -> Dict[str, Any]:
    """arch §6.2 JSON 스키마와 정확히 일치하는 리포트 dict를 조립한다.

    ``raw_stage``/``catalog_stage``는 독립 필드로 그대로 보존한다(합치지
    않는다 — A-5). ``pending``/``unmapped``도 입력을 그대로 전달할 뿐 서로
    섞지 않는다. 예외를 던지지 않는다 — 내부 오류가 나면 안전한 fallback
    리포트(``scan_error``류)를 반환한다.
    """
    try:
        exit_code = exit_code_for_verdict(verdict)

        raw_stage_out = dict(raw_stage) if raw_stage is not None else _default_raw_stage()
        catalog_stage_out = (
            dict(catalog_stage) if catalog_stage is not None else _default_catalog_stage()
        )
        unmapped_out = list(unmapped) if unmapped is not None else []
        pending_out = list(pending) if pending is not None else []
        dirty_out = list(dirty) if dirty is not None else []
        errors_out = list(errors) if errors is not None else []
        scope_roots_out = list(scope_roots) if scope_roots is not None else []
        anchors_out = list(anchors) if anchors is not None else []
        warning_out = (
            dict(inherited_warning) if inherited_warning is not None else {"kind": None, "text": ""}
        )

        human = build_human_text(
            verdict,
            raw_stage=raw_stage_out,
            catalog_stage=catalog_stage_out,
            detail=detail,
        )

        return {
            "verdict": verdict,
            "exit_code": exit_code,
            "config_source": config_source,
            "scope_roots": scope_roots_out,
            "anchors": anchors_out,
            "raw_stage": raw_stage_out,
            "catalog_stage": catalog_stage_out,
            "unmapped": unmapped_out,
            "pending": pending_out,
            "dirty": dirty_out,
            "errors": errors_out,
            "runtime_status": runtime_status,
            "catalog_lag_count": catalog_lag_count,
            "inherited_warning": warning_out,
            "human": human,
        }
    except Exception as exc:  # noqa: BLE001 - fail-safe, 절대 예외를 밖으로 던지지 않는다
        return {
            "verdict": "scan_error",
            "exit_code": EXIT_SCAN_ERROR,
            "config_source": config_source if isinstance(config_source, str) else "",
            "scope_roots": [],
            "anchors": [],
            "raw_stage": _default_raw_stage(),
            "catalog_stage": _default_catalog_stage(),
            "unmapped": [],
            "pending": [],
            "dirty": [],
            "errors": [f"report.build_report internal error: {exc}"],
            "runtime_status": "FAILED",
            "catalog_lag_count": 0,
            "inherited_warning": {"kind": None, "text": ""},
            "human": "[kompound-snapshot] 내부 오류로 리포트 조립에 실패했습니다.",
        }


# ── stdout/stderr 라우팅 (arch §6.2 확정 계약) ─────────────────────────


def emit_report(
    report: Dict[str, Any],
    *,
    json_mode: bool,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    """`report`(``build_report()`` 결과)를 계약된 스트림으로 출력한다.

    - ``json_mode=True`` (게이트·훅): stdout에 **한 줄 JSON만**(기계 파싱
      전용), stderr에 사람이 읽는 리포트.
    - ``json_mode=False`` (기본/사람 모드): stdout에 사람이 읽는 리포트,
      stderr에는 ``inherited_warning``이 있을 때만 경고 1줄.

    반환값은 ``report["exit_code"]``(호출자가 프로세스 종료 코드로 그대로
    쓴다). 출력 중 예외가 나도 이 함수는 예외를 던지지 않는다 — 최선을 다해
    출력을 시도하고 그래도 exit_code는 반환한다.
    """
    exit_code = int(report.get("exit_code", EXIT_SCAN_ERROR))
    try:
        import sys as _sys

        out = stdout if stdout is not None else _sys.stdout
        err = stderr if stderr is not None else _sys.stderr
        human = report.get("human", "") or ""

        if json_mode:
            out.write(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n")
            if human:
                err.write(human + "\n")
        else:
            out.write(human + "\n")
            warning = report.get("inherited_warning") or {}
            if warning.get("kind"):
                err.write(f"[kompound-snapshot] {warning.get('text', '')}\n")
    except Exception:  # noqa: BLE001 - fail-safe, 출력 실패가 exit_code 반환을 막지 않는다
        pass

    return exit_code
