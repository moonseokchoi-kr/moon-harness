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
from pathlib import Path
from datetime import datetime, timedelta, timezone

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
        "Skill(git-worktree) 를 호출하여 feat/{feature} 브랜치와 worktree 를 생성하세요.\n"
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
}

# ─── 파일 존재 검사 (라벨별 전이 조건) ────────────────────────

def has_spec(project_dir: Path, feature: str) -> bool:
    return bool(list(project_dir.glob("docs/sdd/spec/*.md")))

def has_blocker_pass(project_dir: Path, feature: str) -> bool:
    for f in project_dir.glob("docs/sdd/spec/*.md"):
        try:
            if "BLOCKER_PASS" in f.read_text():
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
        with open(path) as f:
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

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    pipeline_path = project_dir / ".claude/state/pipeline.json"

    try:
        result = decide(stop_data, project_dir, pipeline_path)
    except Exception as e:
        # Fail-safe: 에러 시 무조건 allow
        result = {"continue": True, "suppressOutput": True, "_error": str(e)}

    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
