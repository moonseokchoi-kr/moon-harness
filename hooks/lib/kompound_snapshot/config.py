"""hooks/lib/kompound_snapshot/config.py — F16 설정 해석 (단일 진입점).

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` §6.1
(이하 "arch"로 인용), §3.2 모듈 계약 표 `config` 행.

`resolve_config()`가 단일 진실 지점이다. 해석 순서(arch §6.1):

    ① 환경변수 → ② 설정 파일(②-a 프로젝트 → ②-b 홈) → ③ 자동 탐색 → ④ 코드 기본값

병합은 **키 단위**다(파일 전체 우선이 아니다 — J-10, arch §6.1 📌). 스칼라
필드(`kompound_repo`/`scan_root`/`max_anchor_depth`/`state_max_age_hours`)는
"가장 높은 우선순위에서 값이 존재하는 소스"를 채택한다. `prefix_map`은 낮은
우선순위 → 높은 우선순위 순 dict 병합이며, 값이 `null`이면 그 키를 삭제한다
(F12 경로 — 미등록으로 되돌림).

Fail-safe 규약(패키지 전체 규약, `__init__.py` 참조): 이 모듈의 유일한 공개
함수 `resolve_config()`는 **예외를 밖으로 던지지 않는다.** 무엇이 해석됐는지는
항상 구조화된 dict(`{"ok": bool, ...}`)로 반환한다. `ok`는 "해석 도중 예기치
못한 오류가 없었는가"가 아니라 **"`kompound_repo`가 해석됐는가"** 를 뜻한다
(arch §6.1 "해석 실패의 의미 분리": `kompound_repo` 미해석 → 기능 전체
비활성 = `ok: False`류 신호). `scan_root` 미해석은 별도 사안이다 — workspace
스코프만 사용 불가할 뿐 기능 자체는 살아있다(T1/T2가 쓰는 repo/worktree
스코프는 `scan_root` 없이도 정상 작동).

이 모듈은 **미설정 안내 출력 여부를 판단하지 않는다.** "미설정"이라는 사실만
반환하고, 안내를 몇 번 냈는지·억제할지는 `runtime_state.py`(T-7)의 단독
책임이다(M-18, arch §6.1 "④ 미설정 안내 '1회'의 기억 위치").

이 모듈은 상태를 갖지 않는다(순수) — 동일 입력(env·파일·`project_root`)에는
항상 동일 출력을 낸다. 자동 탐색 결과도 캐시하지 않는다(arch §6.1 ③-5:
"탐색 결과는 캐시하지 않는다").

**설계 결정 사항 (arch에 없어 이 태스크가 직접 결정 — 후속 태스크 참고)**:

1. `DEFAULT_PREFIX_MAP`을 arch §6.1은 "`naming.py`의 상수 테이블"로 제안했지만,
   Wave 1에서 `config`(T-3)와 `naming`(T-4)이 **동시에 병렬 구현**되므로
   `config.py`가 아직 존재하지 않는 `naming.py`를 import하면(또는 그 반대)
   레이스가 생긴다. 이 상수는 `config.py`가 `prefix_map` 병합의 최하위
   소스로 반드시 자체 보유해야 하는 데이터이기도 하므로, 이 태스크는
   `DEFAULT_PREFIX_MAP`을 **이 파일에** 정의했다. `naming.py`(T-4)는 이
   상수를 자체 재정의하지 말고 `from hooks.lib.kompound_snapshot.config
   import DEFAULT_PREFIX_MAP`으로 재사용하는 것을 권장한다(단일 진실 유지) —
   T-11 통합 시 재확인 필요.
2. `HARNESS_KOMPOUND_CONFIG`(설정 파일 경로 직접 지정)로 로드된 값의
   `source` 태그는 `"project"`로 기록한다. arch/task 문서는 이 환경변수가
   "②의 탐색(②-a·②-b 둘 다)을 대체한다"고만 명시하고 `source` 라벨을
   지정하지 않았다 — ②-a(프로젝트 파일)와 동일한 우선순위 슬롯을 대체하는
   것으로 해석해 `"project"`를 재사용했다(가능한 값이 `env|project|home|
   discovery` 4종으로 고정돼 있어 새 라벨을 만들지 않았다).
3. `prefix_map`의 `source` 값은 개별 키 단위가 아니라 `"default"`(기본값만
   사용됨) 또는 `"merged"`(홈/프로젝트 파일이 하나 이상의 키를 오버라이드함)
   로 요약한다 — `prefix_map`은 여러 소스가 키 단위로 기여하는 dict라
   스칼라 필드와 같은 단일 소스 라벨이 성립하지 않는다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from hooks.lib.self_improve.state_io import load_state

__all__ = ["DEFAULT_PREFIX_MAP", "resolve_config"]

PathLike = Union[str, "Path"]

# ── F4 기본 프리픽스 매핑 (spec F4 10종 프리픽스, arch §6.1 최하위 병합 소스) ──
# home repo 디렉토리명 → kompound raw 파일명 접두어. 코드가 아니라 "데이터"로
# 보유한다(F16) — 사용자가 설정 파일로 교체·확장할 수 있어야 한다.
DEFAULT_PREFIX_MAP: Dict[str, str] = {
    "Marvelous": "marvelous",
    "Marvelous_dev": "marvelous",
    "Marvelous_feature": "marvelous",
    "Marvelous_code_review": "marvelous",
    "auto-fix-base": "marvelous",
    "CLOFab_Web": "clofab",
    "Marvelous_graphify": "graphify",
    "auto-fix-orchestrator": "autofix",
    "crash-ai-analysis": "crashai",
    "codegraph-clo": "codegraph",
    "ai-code-reviewer-action": "aireview",
    "moon-harness": "harness",
    "rein": "rein",
    "claude-slack-channel": "slack",
}

# ── 환경변수 키 (arch §6.1 확정) ─────────────────────────────────────────────
_ENV_KOMPOUND_REPO = "HARNESS_KOMPOUND_REPO"
_ENV_SCAN_ROOT = "HARNESS_KOMPOUND_SCAN_ROOT"
_ENV_CONFIG_PATH = "HARNESS_KOMPOUND_CONFIG"
_ENV_CLAUDE_CONFIG_DIR = "CLAUDE_CONFIG_DIR"
_ENV_CLAUDE_PROJECT_DIR = "CLAUDE_PROJECT_DIR"

# ── 설정 파일 위치 (arch §6.1 확정 — `.claude/state/` 밖) ───────────────────
_HOME_CONFIG_FILENAME = "kompound-snapshot.json"
_PROJECT_CONFIG_RELATIVE = Path(".claude") / "kompound-snapshot.config.json"

# ── 코드 기본값 (④, arch §6.1 JSON 스키마) ──────────────────────────────────
_DEFAULT_MAX_ANCHOR_DEPTH = 5
_DEFAULT_STATE_MAX_AGE_HOURS = 24

_SCALAR_FIELDS: Tuple[str, ...] = (
    "kompound_repo",
    "scan_root",
    "max_anchor_depth",
    "state_max_age_hours",
)

# kompound 서명(arch §6.1 ③-2) — 이름이 아니라 구조로 식별한다.
_SIGNATURE_GIT = ".git"
_SIGNATURE_RAW_DIR = "raw"
_SIGNATURE_WIKI_INDEX = Path("wiki") / "index.md"
_SIGNATURE_WIKI_LOG = Path("wiki") / "log.md"


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────


def _home_config_dir() -> Path:
    """`${CLAUDE_CONFIG_DIR:-~/.claude}` — 홈 설정 파일이 사는 디렉토리."""
    override = os.environ.get(_ENV_CLAUDE_CONFIG_DIR) or None
    if override:
        return Path(override)
    return Path.home() / ".claude"


def _load_config_file(path: Path) -> Optional[Dict[str, Any]]:
    """JSON 설정 파일을 로드한다.

    부재·파싱 실패·최상위가 dict가 아닌 경우 전부 `None`(값 없음)으로
    처리한다 — 예외를 던지지 않는다(fail-safe, F16 완료조건).
    `hooks.lib.self_improve.state_io.load_state`를 그대로 재사용한다(arch §4
    단방향 허용 의존 — 원자적 write/로드 유틸 중복 구현 회피).
    """
    data = load_state(path)
    if not isinstance(data, dict):
        return None
    return data


def _read_env_scalars() -> Dict[str, Optional[str]]:
    """① 환경변수 스칼라 2종(`kompound_repo`/`scan_root`)을 읽는다."""
    return {
        "kompound_repo": os.environ.get(_ENV_KOMPOUND_REPO) or None,
        "scan_root": os.environ.get(_ENV_SCAN_ROOT) or None,
    }


def _kompound_signature_ok(candidate: Path) -> bool:
    """`candidate`가 kompound 서명(arch §6.1 ③-2 4조건)을 만족하는가.

    이름이 아니라 구조로 판정한다 — AGENTS.md가 규정한 kompound의 필수
    구조(git 저장소 + `raw/` + `wiki/index.md` + `wiki/log.md`)를 그대로
    검사한다. 파일시스템 오류(권한 등)는 미충족으로 처리한다.
    """
    try:
        if not candidate.is_dir():
            return False
        if not (candidate / _SIGNATURE_GIT).exists():
            return False
        if not (candidate / _SIGNATURE_RAW_DIR).is_dir():
            return False
        if not (candidate / _SIGNATURE_WIKI_INDEX).is_file():
            return False
        if not (candidate / _SIGNATURE_WIKI_LOG).is_file():
            return False
        return True
    except OSError:
        return False


def _discover_kompound(project_root: Path) -> Optional[Path]:
    """③ 자동 탐색 (arch §6.1). 후보 = `project_root` 부모의 직속 자식(1단계).

    서명 통과 후보가 정확히 1개면 채택, 0개/2개 이상이면 `None`(미해석 —
    추측하지 않는다). 결과는 호출자가 캐시하지 않는 한 매 호출 재계산된다
    (이 함수 자체도 캐시하지 않는다 — arch §6.1 ③-5).
    """
    try:
        parent = project_root.resolve().parent
        if not parent.is_dir():
            return None
        candidates = [child for child in parent.iterdir() if _kompound_signature_ok(child)]
    except OSError:
        return None

    if len(candidates) != 1:
        return None
    return candidates[0]


def _is_root_path(path: Path) -> bool:
    """`path`가 파일시스템 루트인가(`/`, `C:\\` 등 — OS 불문 일반 판정)."""
    return path.parent == path


def _reject_scan_root(path: Path) -> bool:
    """`scan_root` 후보가 `/` 또는 사용자 홈 디렉토리 자체면 거부한다(arch §6.1 ③-4)."""
    try:
        resolved = path.resolve()
    except OSError:
        return True
    if _is_root_path(resolved):
        return True
    try:
        if resolved == Path.home().resolve():
            return True
    except OSError:
        pass
    return False


def _merge_scalar(
    field: str, sources: List[Tuple[str, Optional[Dict[str, Any]]]]
) -> Tuple[Any, Optional[str]]:
    """`sources`(우선순위 높은 순 `(source_name, dict)` 리스트)에서 `field`의
    non-null 값을 가진 첫 소스를 채택한다. 없으면 `(None, None)`."""
    for source_name, data in sources:
        if not data:
            continue
        value = data.get(field)
        if value is not None:
            return value, source_name
    return None, None


def _merge_prefix_map(sources_low_to_high: List[Optional[Dict[str, Any]]]) -> Dict[str, str]:
    """`prefix_map`을 낮은 우선순위 → 높은 우선순위 순으로 dict 병합한다.

    값이 `null`이면 그 키를 삭제한다(F12 경로 — 미등록으로 되돌림).
    `DEFAULT_PREFIX_MAP`이 항상 최하위 소스로 참여한다(arch §6.1).
    """
    merged: Dict[str, str] = dict(DEFAULT_PREFIX_MAP)
    for data in sources_low_to_high:
        if not data:
            continue
        prefix_map = data.get("prefix_map")
        if not isinstance(prefix_map, dict):
            continue
        for key, value in prefix_map.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
    return merged


def _default_project_root() -> Path:
    """`project_root` 미지정 시 기본값 — `CLAUDE_PROJECT_DIR` 우선, 없으면 cwd.

    이 레포의 기존 어댑터 관례(`stop-pipeline.py`의
    `os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())`)와 동일하다.
    """
    return Path(os.environ.get(_ENV_CLAUDE_PROJECT_DIR, os.getcwd()))


def _empty_result(error: Optional[str] = None) -> Dict[str, Any]:
    """fail-safe 기본 결과 — 아무것도 해석되지 않은 상태와 동일한 모양."""
    result: Dict[str, Any] = {
        "ok": False,
        "kompound_repo": None,
        "scan_root": None,
        "max_anchor_depth": _DEFAULT_MAX_ANCHOR_DEPTH,
        "state_max_age_hours": _DEFAULT_STATE_MAX_AGE_HOURS,
        "prefix_map": dict(DEFAULT_PREFIX_MAP),
        "source": {
            "max_anchor_depth": "default",
            "state_max_age_hours": "default",
            "prefix_map": "default",
        },
    }
    if error is not None:
        result["error"] = error
    return result


# ── 공개 API ─────────────────────────────────────────────────────────────────


def resolve_config(project_root: Optional[PathLike] = None) -> Dict[str, Any]:
    """F16 설정 해석의 단일 진입점.

    해석 순서: ① 환경변수 → ② 설정 파일(②-a 프로젝트 → ②-b 홈) → ③ 자동
    탐색 → ④ 코드 기본값. 키 단위 병합(파일 전체 우선이 아님).

    Args:
        project_root: 프로젝트 루트 절대/상대 경로. 생략하면
            `CLAUDE_PROJECT_DIR` 환경변수, 그마저 없으면 `os.getcwd()`를 쓴다.

    Returns:
        ``{"ok": bool, "kompound_repo": str|None, "scan_root": str|None,
        "max_anchor_depth": int, "state_max_age_hours": int,
        "prefix_map": dict, "source": dict}``. 예외를 던지지 않는다 —
        예기치 못한 오류는 이 모양의 빈 결과(`ok: False`)로 흡수한다.
    """
    try:
        return _resolve_config_impl(project_root)
    except Exception as exc:  # noqa: BLE001 — fail-safe, 밖으로 던지지 않는다
        return _empty_result(error=str(exc))


def _resolve_config_impl(project_root: Optional[PathLike]) -> Dict[str, Any]:
    root = Path(project_root) if project_root is not None else _default_project_root()

    env_scalars = _read_env_scalars()

    # ②: 설정 파일. HARNESS_KOMPOUND_CONFIG가 지정되면 ②-a/②-b 탐색 전체를
    # 대체한다(그 경로 하나만 읽는다) — arch §6.1 환경변수 표.
    config_path_override = os.environ.get(_ENV_CONFIG_PATH) or None
    if config_path_override:
        project_file = _load_config_file(Path(config_path_override))
        home_file: Optional[Dict[str, Any]] = None
    else:
        project_file = _load_config_file(root / _PROJECT_CONFIG_RELATIVE)
        home_file = _load_config_file(_home_config_dir() / _HOME_CONFIG_FILENAME)

    resolved: Dict[str, Any] = {}
    source: Dict[str, str] = {}

    for field in _SCALAR_FIELDS:
        candidates: List[Tuple[str, Optional[Dict[str, Any]]]] = []
        if field in ("kompound_repo", "scan_root"):
            candidates.append(("env", env_scalars))
        candidates.append(("project", project_file))
        candidates.append(("home", home_file))
        value, src = _merge_scalar(field, candidates)
        resolved[field] = value
        if src is not None:
            source[field] = src

    # ③ 자동 탐색 — kompound_repo가 아직 미해석일 때만 시도한다. 채택되면
    # scan_root도 미해석인 경우에 한해 같이 채운다(arch §6.1 ③-4).
    if resolved.get("kompound_repo") is None:
        discovered = _discover_kompound(root)
        if discovered is not None:
            resolved["kompound_repo"] = str(discovered)
            source["kompound_repo"] = "discovery"
            if resolved.get("scan_root") is None:
                scan_root_candidate = discovered.parent
                if not _reject_scan_root(scan_root_candidate):
                    resolved["scan_root"] = str(scan_root_candidate)
                    source["scan_root"] = "discovery"

    # ④ 코드 기본값 — max_anchor_depth/state_max_age_hours만 해당한다.
    # kompound_repo/scan_root는 "기본값"이 없다(미해석 = 미해석).
    if resolved.get("max_anchor_depth") is None:
        resolved["max_anchor_depth"] = _DEFAULT_MAX_ANCHOR_DEPTH
        source["max_anchor_depth"] = "default"
    if resolved.get("state_max_age_hours") is None:
        resolved["state_max_age_hours"] = _DEFAULT_STATE_MAX_AGE_HOURS
        source["state_max_age_hours"] = "default"

    # prefix_map: 낮음 → 높음 순 dict 병합(default가 이미 최하위로 내장돼 있음).
    prefix_overridden = any(
        isinstance(data, dict) and isinstance(data.get("prefix_map"), dict) and data.get("prefix_map")
        for data in (home_file, project_file)
    )
    resolved["prefix_map"] = _merge_prefix_map([home_file, project_file])
    source["prefix_map"] = "merged" if prefix_overridden else "default"

    resolved["ok"] = resolved.get("kompound_repo") is not None
    resolved["source"] = source

    # 반환 키 순서를 arch §3.2 계약 표와 맞춘다(가독성 목적, 기능에는 무관).
    return {
        "ok": resolved["ok"],
        "kompound_repo": resolved["kompound_repo"],
        "scan_root": resolved["scan_root"],
        "max_anchor_depth": resolved["max_anchor_depth"],
        "state_max_age_hours": resolved["state_max_age_hours"],
        "prefix_map": resolved["prefix_map"],
        "source": resolved["source"],
    }
