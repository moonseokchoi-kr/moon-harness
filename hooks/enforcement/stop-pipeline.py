#!/usr/bin/env python3
"""
enforcement/stop-pipeline.py — Stop 훅 파이프라인 컨트롤러

SDD 워크플로우의 Phase 간 자동 전환을 담당한다.
pipeline.json의 current_label을 읽고 다음 액션을 지시하여
Claude가 수동 개입 없이 Phase 1 → Phase 4 진입까지 자동 진행하도록 한다.

참고: oh-my-claudecode/scripts/persistent-mode.cjs의 우선순위 기반
     circuit breaker + session 격리 + context limit fail-safe 패턴 차용.

입력 (stdin):
  JSON with Stop hook data from Claude Code

출력 (stdout):
  JSON — {"decision": "block", "reason": "..."} or {"continue": true}
"""

import sys
import os
import json
import time
import tempfile
import shutil
import glob
import io
import contextlib
from pathlib import Path
from datetime import datetime, timedelta, timezone


def _winify_path(p: str) -> str:
    """Git-bash/MSYS '/c/foo' 경로를 'C:/foo' 로 정규화한다 (Windows 전용).

    네이티브 Windows Python 은 '/c/foo' 를 'C:\\c\\foo' 로 잘못 해석해 파일을
    못 연다. macOS/Linux(os.name != 'nt') 와 이미 Windows 형식인 경로엔 무변경.
    """
    if (
        os.name == "nt"
        and len(p) >= 2
        and p[0] == "/"
        and p[1].isalpha()
        and (len(p) == 2 or p[2] == "/")
    ):
        return p[1].upper() + ":" + p[2:]
    return p


# ─── kompound 박제 완료 게이트(F1, T-12) — 코어 import 부트스트랩 ──────
# arch §5.1.1/§5.1.2: `stop-pipeline.sh`는 `exec python3 "$SCRIPT_DIR/..."`만
# 하고 PYTHONPATH를 설정하지 않는다. 부트스트랩 없이는 이 스크립트 안에서
# `hooks.lib.kompound_snapshot`을 import할 수 없다(ModuleNotFoundError).
# 여기서는 sys.path 부작용만 만든다 — 실제 import는 게이트 함수 내부에서
# 지연 수행한다(무장 안 된 대다수 호출에서 import 비용 0, import 실패가
# 이 모듈 로드 자체를 깨뜨리지 않도록. F17 안전망이 "부트스트랩 후에도 기존
# Step 0~9 동작이 입력별로 불변"임을 고정한다).
def _resolve_kompound_plugin_root() -> Path:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(_winify_path(env_root))
    return Path(__file__).resolve().parents[2]


_KOMPOUND_PLUGIN_ROOT = _resolve_kompound_plugin_root()
if str(_KOMPOUND_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_KOMPOUND_PLUGIN_ROOT))


# ─── 상수 ──────────────────────────────────────────────────────

SCHEMA_VERSION = 1

# Circuit breaker
CB_MAX_BLOCKS = 20
CB_TTL_MINUTES = 5

# Stale state
STALE_THRESHOLD_HOURS = 2

# Context limit
CONTEXT_LIMIT_PCT = 90

# ─── 라벨 → 다음 액션 지시문 ───────────────────────────────────

DIRECTIVES = {
    "PHASE1_UX_RESEARCH_DONE": (
        "[SDD-PIPELINE] Phase 1 시작.\n"
        "Agent(sdd-ux-researcher) 를 디스패치하여 spec 문서를 작성하세요.\n"
        "저장 경로: docs/sdd/spec/{YYYY-MM-DD}-{feature}.md\n"
        "완료 후 pipeline.json 의 current_label 을 PHASE1_SPEC_DRAFT 로 갱신하세요."
    ),
    "PHASE1_SPEC_DRAFT": (
        "[SDD-PIPELINE] spec 작성 완료.\n"
        "Agent(sdd-blocker-checker) 를 디스패치하여 블로커 검사하세요.\n"
        "PASS 시: spec 말미에 'BLOCKER_PASS' 마크 추가 후 current_label 을 PHASE1_BLOCKER_CHECK_PASS 로 갱신.\n"
        "BLOCKED 시: spec 보완 후 재검사."
    ),
    "PHASE1_BLOCKER_CHECK_PASS": (
        "[SDD-PIPELINE] 블로커 통과. 사용자 승인 필요.\n"
        "다음을 수행하세요:\n"
        "1. spec 문서 요약을 사용자에게 제시\n"
        "2. pipeline.json 에서 waiting_for_user=true, waiting_for_approval_type='spec' 설정\n"
        "3. 사용자 응답 대기 (자연어 '승인', '좋아', '진행' 등)\n"
        "4. 승인 시 current_label=PHASE1_USER_APPROVED, waiting_for_user=false"
    ),
    "PHASE1_USER_APPROVED": (
        "[SDD-PIPELINE] Phase 1 완료. Phase 2 시작.\n"
        "current_label 을 PHASE2_START 로 갱신하세요."
    ),
    "PHASE2_START": (
        "[SDD-PIPELINE] Phase 2 시작. Worktree 생성 필요.\n"
        "Skill(git-worktree) 를 호출하여 feature/{feature} 브랜치와 worktree 를 생성하세요.\n"
        "완료 후 pipeline.json 의 worktree_path 기록 + current_label=PHASE2_WORKTREE_CREATED."
    ),
    "PHASE2_WORKTREE_CREATED": (
        "[SDD-PIPELINE] Worktree 준비 완료. 아키텍처 설계 필요.\n"
        "프로젝트 스택 감지 후 적절한 architect 디스패치:\n"
        "- Flutter: flutter-architect\n"
        "- React/Vue/Next: webapp-architect\n"
        "- Rust/C++: native-architect\n"
        "완료 후 sdd-architect-reviewer 로 리뷰 → PASS → current_label=PHASE2_ARCH_STRUCTURE_DONE."
    ),
    "PHASE2_ARCH_STRUCTURE_DONE": (
        "[SDD-PIPELINE] 아키텍처 설계 완료. 사용자 승인 필요.\n"
        "1. 아키텍처 구조 요약을 사용자에게 제시\n"
        "2. waiting_for_user=true, approval_type='arch' 설정\n"
        "3. 승인 시 current_label=PHASE2_ARCH_USER_APPROVED"
    ),
    "PHASE2_ARCH_USER_APPROVED": (
        "[SDD-PIPELINE] 아키텍처 승인됨.\n"
        "모드에 따라 분기:\n"
        "- FULL 모드: Agent(sdd-ui-designer) 디스패치 + e2e-config.json 생성 → current_label=PHASE2_UI_DESIGN_COMPLETE\n"
        "- SIMPLE 모드: UI/API 건너뛰고 current_label=PHASE2_DESIGN_USER_APPROVED"
    ),
    "PHASE2_UI_DESIGN_COMPLETE": (
        "[SDD-PIPELINE] UI 명세 완료. 사용자 승인 필요.\n"
        "1. UI 명세 + Stitch 링크를 사용자에게 제시\n"
        "2. waiting_for_user=true, approval_type='ui' 설정\n"
        "3. 승인 시 Agent(sdd-api-designer) 디스패치 → current_label=PHASE2_API_DESIGN_COMPLETE"
    ),
    "PHASE2_API_DESIGN_COMPLETE": (
        "[SDD-PIPELINE] API 명세 완료. 사용자 승인 필요.\n"
        "1. API 계약을 사용자에게 제시\n"
        "2. waiting_for_user=true, approval_type='api' 설정\n"
        "3. 승인 시 current_label=PHASE2_DESIGN_USER_APPROVED"
    ),
    "PHASE2_DESIGN_USER_APPROVED": (
        "[SDD-PIPELINE] 전체 설계 승인됨.\n"
        "FULL 모드: Agent(sdd-context-manager) 디스패치하여 context 문서 생성.\n"
        "완료 후 current_label=PHASE2_USER_APPROVED."
    ),
    "PHASE2_USER_APPROVED": (
        "[SDD-PIPELINE] Phase 2 완료. Phase 3 시작.\n"
        "current_label 을 PHASE3_PLAN_START 로 갱신하세요."
    ),
    "PHASE3_PLAN_START": (
        "[SDD-PIPELINE] Phase 3 시작. 태스크 문서 생성 필요.\n"
        "Agent(sdd-taskmaster, mode='tasks') 를 디스패치하세요.\n"
        "완료 후 current_label=PHASE3_TASKMASTER_DONE."
    ),
    "PHASE3_TASKMASTER_DONE": (
        "[SDD-PIPELINE] 태스크 문서 생성 완료. DAG 구성 필요.\n"
        "Agent(sdd-taskmaster, mode='dag') 를 디스패치하여 ORCHESTRATOR_STATE.md 를 생성하세요.\n"
        "완료 후 current_label=PHASE3_DAG_CONSTRUCTED."
    ),
    "PHASE3_DAG_CONSTRUCTED": (
        "[SDD-PIPELINE] DAG 구성 완료. 사용자 승인 필요.\n"
        "1. 태스크 목록 + Wave 구성 + 예상 시간을 사용자에게 제시\n"
        "2. waiting_for_user=true, approval_type='plan' 설정\n"
        "3. 승인 시 current_label=PHASE3_USER_APPROVED"
    ),
    "PHASE3_USER_APPROVED": (
        "[SDD-PIPELINE] Phase 3 완료. Phase 4 진입.\n"
        "다음을 수행하세요:\n"
        "1. git commit --allow-empty -m 'chore: Phase 4 실행 시작'\n"
        "2. pipeline.json 의 current_label=PHASE4_WORKTREE_CREATED 로 갱신\n"
        "3. Skill(sdd-orchestrator) 를 호출하여 Wave/Task 실행을 위임\n"
        "파이프라인은 여기서 종료됩니다. 이후 Stop 훅은 개입하지 않습니다."
    ),
    "PHASE4_WORKTREE_CREATED": None,  # 터미널

    # ── kompound 박제 완료 게이트 전용 (F1, T-12) ──────────────────────
    # 선형 라벨 체인의 원소가 아니다(arch §5.1.2) — decide()가 current_label
    # 로 조회하지 않으며, _kompound_completion_gate()만 이 키를 직접 조회해
    # directive 문자열 템플릿으로 쓴다. 치환은 str.format이 아니라
    # str.replace로 한다 — 위 기존 directive 값들이 `{YYYY-MM-DD}` 같은
    # 리터럴 중괄호를 포함해 format이 KeyError로 죽는다(arch §5.1.2 📌).
    "PHASE4_KOMPOUND_SNAPSHOT_PENDING": (
        "[SDD-PIPELINE] Phase 4 완료 감지 — kompound 박제(F1)가 아직 끝나지 않았습니다.\n"
        "지금 아래 명령을 실행해 SDD 산출물을 kompound 위키에 박제하세요(@@SCOPE@@):\n"
        "  @@CLI@@\n"
        "실행 후 성공/실패 결과를 사용자에게 보고하세요. 실패하더라도 사이클을 되돌리지 말고 "
        "사용자 판단을 요청하세요.\n"
        "self-improve(Step 5)보다 반드시 먼저 끝내세요."
    ),
}

# ─── 파일 존재 검사 (라벨별 전이 조건) ────────────────────────

def has_spec(project_dir: Path, feature: str) -> bool:
    return bool(list(project_dir.glob("docs/sdd/spec/*.md")))

def has_blocker_pass(project_dir: Path, feature: str) -> bool:
    for f in project_dir.glob("docs/sdd/spec/*.md"):
        try:
            if "BLOCKER_PASS" in f.read_text(encoding="utf-8"):
                return True
        except Exception:
            continue
    return False

def has_worktree(project_dir: Path, feature: str, worktree_path: str) -> bool:
    if not worktree_path:
        return False
    return Path(worktree_path).is_dir()

def has_arch(project_dir: Path, feature: str) -> bool:
    return bool(list(project_dir.glob("docs/sdd/design/arch/*.md")))

def has_ui(project_dir: Path, feature: str) -> bool:
    return bool(list(project_dir.glob("docs/sdd/design/ui/*.md")))

def has_api(project_dir: Path, feature: str) -> bool:
    return bool(list(project_dir.glob("docs/sdd/design/api/*.md")))

def has_context(project_dir: Path, feature: str) -> bool:
    return bool(list(project_dir.glob("docs/sdd/context/*.md")))

def has_tasks(project_dir: Path, feature: str) -> bool:
    return bool(list(project_dir.glob(f"docs/sdd/task/{feature}/T-*.md")) or
                list(project_dir.glob("docs/sdd/task/*/T-*.md")))

def has_orchestrator_state(project_dir: Path) -> bool:
    return (project_dir / "docs/sdd/ORCHESTRATOR_STATE.md").exists()


# ─── 상태 파일 I/O ─────────────────────────────────────────────

def load_state(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def atomic_write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, delete=False, suffix=".tmp", encoding="utf-8"
    ) as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    shutil.move(tmp_path, str(path))


# ─── 시간 유틸 ─────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def parse_iso(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def is_stale(state: dict) -> bool:
    last = parse_iso(state.get("last_updated", ""))
    if not last:
        return False
    age = datetime.now(timezone.utc) - last
    return age > timedelta(hours=STALE_THRESHOLD_HOURS)


# ─── 검사 함수 (우선순위 순) ───────────────────────────────────

def check_context_limit(stop_data: dict) -> bool:
    """Context limit 감지 — stop_reason 또는 usage 기반"""
    reason = (stop_data.get("stop_reason") or "").lower().replace(" ", "_").replace("-", "_")
    patterns = ["context_limit", "context_window", "token_limit", "max_tokens"]
    if any(p in reason for p in patterns):
        return True

    usage = stop_data.get("context_usage_percent", 0)
    try:
        return float(usage) >= CONTEXT_LIMIT_PCT
    except (ValueError, TypeError):
        return False

def check_session_match(state: dict, current_session_id: str) -> bool:
    """session_id 매칭 — 다른 세션이면 통과"""
    prev = state.get("session_id")
    if not prev:
        return True  # legacy compat
    if not current_session_id:
        return True  # 세션 정보 없으면 통과 허용
    return prev == current_session_id

def check_circuit_breaker(state: dict) -> tuple:
    """(should_allow, should_reset) 반환"""
    cb = state.get("circuit_breaker", {})
    blocks = cb.get("blocks", 0)
    reset_at_str = cb.get("reset_at", "")

    # TTL 만료 시 reset
    reset_at = parse_iso(reset_at_str)
    if reset_at and datetime.now(timezone.utc) > reset_at:
        return (False, True)  # reset 필요

    # 최대 횟수 초과 시 allow (무한 루프 방지)
    if blocks >= CB_MAX_BLOCKS:
        return (True, True)  # allow + reset

    return (False, False)

def increment_breaker(state: dict):
    cb = state.get("circuit_breaker", {})
    cb["blocks"] = cb.get("blocks", 0) + 1
    cb["max_blocks"] = CB_MAX_BLOCKS
    cb["reset_at"] = (datetime.now(timezone.utc) + timedelta(minutes=CB_TTL_MINUTES)).isoformat()
    state["circuit_breaker"] = cb

def reset_breaker(state: dict):
    state["circuit_breaker"] = {
        "blocks": 0,
        "max_blocks": CB_MAX_BLOCKS,
        "reset_at": (datetime.now(timezone.utc) + timedelta(minutes=CB_TTL_MINUTES)).isoformat()
    }


# ─── 라벨 전이 조건 검증 ───────────────────────────────────────

def label_prerequisite_met(label: str, state: dict, project_dir: Path) -> tuple:
    """
    현재 라벨의 전이 선행조건이 충족됐는가?
    반환: (met: bool, reason: str)

    met=True  → 전이 가능 (다음 액션 지시 생성)
    met=False → 전이 불가 (현재 라벨의 전이 조건 미충족)
    """
    feature = state.get("feature", "")
    worktree = state.get("worktree_path", "")

    checks = {
        "PHASE1_SPEC_DRAFT":             lambda: has_spec(project_dir, feature),
        "PHASE1_BLOCKER_CHECK_PASS":     lambda: has_blocker_pass(project_dir, feature),
        "PHASE2_WORKTREE_CREATED":       lambda: has_worktree(project_dir, feature, worktree),
        "PHASE2_ARCH_STRUCTURE_DONE":    lambda: has_arch(project_dir, feature),
        "PHASE2_UI_DESIGN_COMPLETE":     lambda: has_ui(project_dir, feature),
        "PHASE2_API_DESIGN_COMPLETE":    lambda: has_api(project_dir, feature),
        "PHASE2_USER_APPROVED":          lambda: (
            has_context(project_dir, feature) if state.get("mode") == "FULL" else True
        ),
        "PHASE3_TASKMASTER_DONE":        lambda: has_tasks(project_dir, feature),
        "PHASE3_DAG_CONSTRUCTED":        lambda: has_orchestrator_state(project_dir),
    }

    if label not in checks:
        return (True, "")  # 파일 검증 불필요한 라벨 (user_gate, transition-only)

    try:
        if checks[label]():
            return (True, "")
        return (False, f"[{label}] 선행 파일이 아직 없습니다. directive 를 따라 생성하세요.")
    except Exception as e:
        return (True, "")  # fail-safe: 검증 에러 시 진행 허용


# ─── kompound 박제 완료 게이트 (F1, T-12) ──────────────────────
# 설계 SSOT: docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md §5.1
# (F1 — T1 통합 전체). decide()의 Step 0(context limit) 직후, Step 1
# (pipeline.json 로드) 이전에 호출된다 — pipeline.json을 읽지도 쓰지도
# 않는다(C3, §5.1.1). 판정 자체(무장 조건·상태 전이·블록 예산·
# CATALOG_PENDING 패스스루·A-1)는 전부 runtime_state.record_and_decide()에
# 위임한다 — 이 함수는 입력을 조립해 넘기고 반환값을 Stop 훅 프로토콜
# 모양으로 번역할 뿐, 판정 로직을 복제하지 않는다. increment_breaker나
# CB_MAX_BLOCKS도 쓰지 않는다(§5.1.4 — 자체 예산은 runtime_state가 관리하며,
# 그 state는 Step 1에서 로드되는 pipeline.json 기반이라 이 게이트보다 뒤다).


def _kompound_directive_text(plugin_root: Path, project_dir: Path) -> str:
    """`DIRECTIVES["PHASE4_KOMPOUND_SNAPSHOT_PENDING"]` 템플릿의 @@CLI@@/
    @@SCOPE@@ 토큰을 실행 가능한 값으로 치환한다. `str.format`은 쓰지 않는다
    (모듈 상단 DIRECTIVES 주석 참조 — 리터럴 중괄호가 있는 기존 directive와
    같은 딕셔너리에 있으므로 이 값도 `str.replace` 관례를 따른다)."""
    cli_cmd = (
        f'PYTHONPATH="{plugin_root}" python3 -m hooks.lib.kompound_snapshot apply --json'
    )
    text = DIRECTIVES["PHASE4_KOMPOUND_SNAPSHOT_PENDING"]
    text = text.replace("@@CLI@@", cli_cmd)
    text = text.replace("@@SCOPE@@", f"repo 스코프, project_root={project_dir}")
    return text


def _kompound_check_pending(ks_cli_module, project_dir: Path) -> tuple:
    """`cli.py`의 `check` 서브커맨드를 in-process로 호출해 (pending_count,
    unmapped_count)를 얻는다(부작용 없음 — T-11 확정 계약).

    `cli.main()`은 `report.emit_report()`를 통해 실제 stdout/stderr에 쓴다.
    Stop 훅은 "stdout에 한 줄 JSON만" 규약이므로, 여기서는 stdout/stderr를
    임시로 가로채 흡수한 뒤 캡처된 JSON만 파싱한다 — 실제 훅 출력 오염은
    0이다.

    `cli.py`의 `check`는 `--scope-root`를 받지 않는 한 자체적으로
    `CLAUDE_PROJECT_DIR` 환경변수(없으면 cwd)로 프로젝트 루트를 다시
    계산한다(이 모듈이 그 값을 인자로 넘겨받을 방법이 없다 — arch/task에
    없어 이 태스크가 직접 내린 결정). 호출 전 그 환경변수를 `project_dir`로
    맞춰 두어, 이 게이트가 판정에 쓰는 `project_dir`과 `check`가 스캔하는
    프로젝트 루트가 어긋나지 않게 한다. 호출 후 원래 값으로 복원한다.
    """
    env_key = "CLAUDE_PROJECT_DIR"
    original = os.environ.get(env_key)
    os.environ[env_key] = str(project_dir)
    try:
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            ks_cli_module.main(["check", "--json"])
        check_report = json.loads(buf_out.getvalue())
    except SystemExit:
        # `cli.main()`은 argparse 사용법 오류에서 SystemExit을 던질 수 있다
        # (`BaseException` — 호출부의 `except Exception:`으로 잡히지 않는다).
        # 이 호출은 항상 고정된 유효 argv(["check", "--json"])만 쓰므로 실제
        # 도달 가능성은 매우 낮지만, 혹시라도 발생하면 이 훅 프로세스 전체가
        # 죽어 stdout에 아무 것도 못 쓰는 것보다는 "판정 불가"로 흡수하는
        # 편이 fail-safe 원칙(§5.1.3 "판정 자체를 못 했음 → 경고 후 통과")에
        # 맞다.
        check_report = {}
    finally:
        if original is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = original
    pending = check_report.get("pending") or []
    unmapped = check_report.get("unmapped") or []
    return len(pending), len(unmapped)


def _kompound_completion_gate(stop_data: dict, project_dir: Path):
    """완료 게이트 본체.

    반환:
      None                                     → 개입하지 않음 (기존 Step 1로 진행)
      {"decision": "block", "reason": "..."}    → 정지 차단

    실패는 전부 통과(None)로 흡수한다 — arch §5.1.3 마지막 두 행("판정 자체를
    못 했음 → 경고 후 통과")과 동일 원칙이다. 이 함수는 `pipeline.json`을
    절대 읽거나 쓰지 않는다.
    """
    orchestrator_state_path = project_dir / "docs" / "sdd" / "ORCHESTRATOR_STATE.md"
    if not orchestrator_state_path.is_file():
        return None  # STATE 문서가 없는 프로젝트 — 게이트 대상 아님(C3 무관)

    # 1단계: 무장(arming) 여부만 싸게 확인한다(성능 P1 수정, T-12 iteration 2,
    # arch §2.3 "무장 안 됨 < 20ms, 코어 import 없음"). `runtime_state` 모듈
    # "하나만" 지연 import한다 — `config`/`cli`(및 그 안의 `resolve_config()`·
    # 전체 워크스페이스 스캔)는 무장이 확정된 뒤에만 import한다.
    #
    # 이렇게 하지 않으면: `ORCHESTRATOR_STATE.md`는 SDD 사이클이 머지되면
    # main에 영구히 남는다(.harness/LEARNING.md 2026-07-01 엔트리). kompound가
    # 설정된 채로 SDD를 한 번이라도 완료한 프로젝트는, 그 이후 그 SDD와
    # 무관한 모든 세션의 모든 Stop 훅 호출마다 전체 스캔 비용을 영구히
    # 지불하게 된다 — 이 사전판정이 그 비용을 없앤다.
    #
    # `is_armed()`는 STATE 서명 비교만 하는 부작용 없는 함수이고,
    # `record_and_decide()`도 내부적으로 같은 구현을 재사용한다(판정 이원화
    # 없음, runtime_state.py 참조) — 여기서 무장이라고 판단해도 최종 판정은
    # 여전히 아래 `record_and_decide()`가 (올바른 config의 state_max_age_hours로)
    # 다시 내린다. 이 사전판정은 순수 최적화이며 판정 결과의 정확성에
    # 영향을 주지 않는다 — 다만 `state_max_age_hours`는 아직 config를 읽지
    # 않았으므로 기본값(24h)으로 확인한다(사용자가 설정 파일로 신선도 상한을
    # 바꾼 경계 케이스에서는 이 사전판정이 실제보다 느슨하게/엄격하게 판단할
    # 수 있으나, 그 경우에도 뒤따르는 진짜 `record_and_decide()` 호출이
    # 정확한 값으로 최종 판정하므로 정답은 항상 보존된다 — 최악의 경우
    # 드물게 불필요한 스캔을 한 번 더 하는 정도의 손해뿐이다).
    try:
        from hooks.lib.kompound_snapshot import runtime_state as _ks_runtime_state
    except Exception:
        return None  # import 실패 — 판정 불가, 차단 없이 통과(§5.1.3)

    try:
        armed_probe = _ks_runtime_state.is_armed(project_dir, orchestrator_state_path)
    except Exception:
        return None

    if not armed_probe.get("armed"):
        # 무장 안 됨 — config/cli import·전체 워크스페이스 스캔은 전부
        # 생략한다(이 최적화가 이 수정의 목적). 그래도 arch §5.1.3 판정표의
        # "무장 안 됨 → 아무것도 안 하고 Step 1로 진행, **baseline만 갱신**"
        # 행은 반드시 실행돼야 한다 — 그렇지 않으면 baseline_signature가
        # 영원히 None으로 남아(첫 관측 등록이 전혀 발생하지 않아) 이 프로젝트
        # 전체 수명 동안 게이트가 단 한 번도 무장되지 못하는 치명적 회귀가
        # 생긴다. `record_and_decide()`를 placeholder 값(`pending_count=0`
        # 등)으로 호출해 그 갱신만 수행시킨다 — 이 함수의 "무장 안 됨" 분기는
        # `pending_count`/`config_ok`를 전혀 참조하지 않으므로(코드 확인
        # 완료) 안전하고, `config`/`cli`를 import하지 않으므로 전체 스캔
        # 비용도 여전히 0이다.
        try:
            _ks_runtime_state.record_and_decide(
                project_dir, orchestrator_state_path, config_ok=False, pending_count=0
            )
        except Exception:
            pass
        return None

    # 2단계: 무장 확정 — 그제서야 config/cli를 import하고 실제 판정을 한다.
    try:
        from hooks.lib.kompound_snapshot import cli as _ks_cli
        from hooks.lib.kompound_snapshot import config as _ks_config
    except Exception:
        return None  # import 실패 — 판정 불가, 차단 없이 통과(§5.1.3)

    try:
        cfg = _ks_config.resolve_config(project_dir)
    except Exception:
        return None

    pending_count = 0
    unmapped_count = 0
    if cfg.get("ok"):
        try:
            pending_count, unmapped_count = _kompound_check_pending(_ks_cli, project_dir)
        except Exception:
            pending_count, unmapped_count = 0, 0

    current_sid = os.environ.get("CLAUDE_SESSION_ID", "") or stop_data.get("session_id", "")

    try:
        result = _ks_runtime_state.record_and_decide(
            project_dir,
            orchestrator_state_path,
            config_ok=bool(cfg.get("ok")),
            pending_count=pending_count,
            unmapped_count=unmapped_count,
            state_max_age_hours=cfg.get("state_max_age_hours"),
            session_id=(current_sid or None),
        )
    except Exception:
        return None

    if not isinstance(result, dict) or result.get("action") != "block":
        return None

    directive = _kompound_directive_text(_KOMPOUND_PLUGIN_ROOT, project_dir)
    message = result.get("message")
    if message:
        directive = f"{directive}\n\n{message}"

    return {"decision": "block", "reason": directive}


# ─── 메인 판정 로직 ────────────────────────────────────────────

def decide(stop_data: dict, project_dir: Path, pipeline_path: Path) -> dict:
    """
    Stop 훅 판정 로직. 반환값이 Claude Code 에 JSON 으로 전달된다.

    반환:
      {"continue": true}                    → 정지 허용
      {"decision": "block", "reason": "..."} → 정지 차단 + reason 주입
    """

    # Step 0: Context limit (최우선 — deadlock 회피)
    if check_context_limit(stop_data):
        return {"continue": True, "suppressOutput": True}

    # Step 0.5: kompound 박제 완료 게이트 (F1, T-12, arch §5.1) —
    # pipeline.json과 독립적이다(C3). is_stale/세션 매칭(Step 2/3)보다
    # 앞에 둔다 — Phase 4는 수 시간~수 세션에 걸쳐 있어 뒤에 두면 발화하지
    # 않는다(C1/C2). 게이트가 개입하지 않으면(None) 기존 Step 1~9 동작은
    # 입력별로 완전히 동일하다(F17 안전망).
    gate_result = _kompound_completion_gate(stop_data, project_dir)
    if gate_result is not None:
        return gate_result

    # Step 1: 상태 파일 로드
    state = load_state(pipeline_path)
    if not state:
        return {"continue": True, "suppressOutput": True}  # 파이프라인 비활성

    # Step 2: Stale state (2시간 미갱신 → 무시)
    if is_stale(state):
        return {"continue": True, "suppressOutput": True}

    # Step 3: Session 격리
    current_sid = os.environ.get("CLAUDE_SESSION_ID", "") or stop_data.get("session_id", "")
    if not check_session_match(state, current_sid):
        return {"continue": True, "suppressOutput": True}

    # Step 4: Circuit breaker
    allow_cb, should_reset = check_circuit_breaker(state)
    if should_reset:
        reset_breaker(state)
        atomic_write(pipeline_path, state)
    if allow_cb:
        return {"continue": True, "suppressOutput": True}

    # Step 5: 터미널 라벨 (Phase 4 진입 완료)
    current_label = state.get("current_label", "")
    if current_label == "PHASE4_WORKTREE_CREATED":
        return {"continue": True, "suppressOutput": True}

    # Step 6: 사용자 승인 대기 중 → Claude 멈춤 허용
    if state.get("waiting_for_user", False):
        return {"continue": True, "suppressOutput": True}

    # Step 7: 현재 라벨의 전이 조건 검사
    met, reason = label_prerequisite_met(current_label, state, project_dir)

    # Step 8: 다음 액션 지시문 생성
    directive = DIRECTIVES.get(current_label)
    if not directive:
        return {"continue": True, "suppressOutput": True}  # 정의 안 된 라벨 → 허용

    # 전이 조건 미충족 시 추가 메시지
    if not met:
        directive = f"{directive}\n\n⚠️ 전이 조건 미충족: {reason}"

    # Step 9: Circuit breaker 증가 + 상태 저장
    increment_breaker(state)
    state["last_updated"] = now_iso()
    state["last_action_directive"] = directive
    atomic_write(pipeline_path, state)

    return {"decision": "block", "reason": directive}


# ─── 엔트리 포인트 ─────────────────────────────────────────────

def main():
    try:
        raw = sys.stdin.read()
        stop_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        stop_data = {}

    project_dir = Path(_winify_path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())))
    pipeline_path = project_dir / ".claude/state/pipeline.json"

    try:
        result = decide(stop_data, project_dir, pipeline_path)
    except Exception as e:
        # Fail-safe: 에러 시 무조건 allow
        result = {"continue": True, "suppressOutput": True, "_error": str(e)}

    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
