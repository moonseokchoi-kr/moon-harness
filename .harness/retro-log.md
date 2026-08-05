# Retro Log (append-only)

`/self-improve` 회고 이력. 회고 1회 = 요약 1줄 + 적용된 프로젝트 티어 변경마다 롤백 블록.
사람이 직접 편집하지 않는다.

---

## 2026-08-05 retro — 신규 12건 처리 / 적용 3 · 제안 4 · 폐기 5

첫 회고 (`retro-state.json` 부재 → 전체가 신규). Phase A에서 **입력 채널 결함**을 먼저 발견:
main의 `.harness/LEARNING.md`에 사이클 교훈이 0건이었고, 아직 살아 있던
`worktrees/kompound-snapshot-hook/.harness/LEARNING.md`에서 4건(T-5/T-10/T-13/T-12)을 회수해
시간순 병합한 뒤 회고를 진행했다. 이번 세션 신호 2건(네이밍 중복 / 훅 오탐)을 추가해 총 12건.
클러스터 10개, **전부 `has_cross_project=False`**(단일 repo `moon-harness` 근거).
critic 배치 판정: UPHELD 1 · NARROW 6 · REFUTED 1.

### 적용 (프로젝트 티어, 자동)

- **`docs/lessons-learned.md`** (신규 생성) ← 결합 verdict 필드 / 네이밍 정합 감사 / 비수렴 승격
  - critic: NARROW(C1) · NARROW(C6a) · **UPHELD**(C6b)
  - 근거: `## 2026-07-30 — kompound-snapshot-hook / T-5-git-state`,
    `## 2026-08-05 — kompound-snapshot / 네이밍 중복 접기 (첫 실전 실행)`
  - rollback: `rm docs/lessons-learned.md` (신규 파일이므로 파일 삭제로 완전 원복)

- **`CLAUDE.local.md`** (신규 생성) ← `@docs/lessons-learned.md` 컨텍스트 포인터
  - 이유: 포인터가 `CLAUDE.md`·`CLAUDE.local.md` 어디에도 없어 승격 문서가 로드되지 않았다
    (Phase D §10 가설-A 갭). committed `CLAUDE.md`는 편집하지 않았다.
    `.gitignore:20`에 `CLAUDE.local.md`가 이미 있어 추가 불필요.
  - rollback: `rm CLAUDE.local.md`

- **`.harness/LEARNING.md`** ← 워크트리 교훈 4건 회수 병합 + T-13 엔트리에 누락된 provenance 태그 삽입
  - 이유: 입력 채널 복구(회고 자체가 불가능한 상태였음). LEARNING.md는 읽기 전용 입력이라는
    규칙의 예외 — 삭제·수정이 아니라 **소실된 엔트리 복원**이며 원문 그대로 병합했다.
  - rollback: `## 2026-07-30 — …T-5-git-state` ~ `## 2026-08-04 — …T-12-stop-pipeline` 4블록 제거
    (원본은 `worktrees/kompound-snapshot-hook/.harness/LEARNING.md`에 그대로 있음)

### 제안 (하네스 티어, 승인 대기)

- `harness-proposals/2026-08-05-learning-recovery-before-worktree-removal.md` —
  `skills/git-worktree/SKILL.md` + `skills/sdd-orchestrator/SKILL.md` /
  **최우선**: 워크트리 삭제 전 LEARNING 헤더-dedup 회수 (자가개선 입력 채널 복구)
- `harness-proposals/2026-08-05-enforcement-hook-false-positive-fixes.md` —
  `hooks/file-ownership.sh` + `hooks/dangerous-command.sh` / 오탐 수정
  (**2 독립 신호 · 사용자 명시 승인 완료 → 구현 스펙으로 사용**)
- `harness-proposals/2026-08-05-sdd-review-checklist-arch-self-verification.md` —
  `agents/sdd-reviewer.md` + `agents/sdd-test-automator.md` + `agents/sdd-architect-reviewer.md` /
  복구 경로 실행 증명 · 프리필터·코어 정합 · 콜드 프로세스 성능 단정 (3항목 통합)
- `harness-proposals/2026-08-05-report-nonconvergent-human-decision.md` —
  `hooks/lib/kompound_snapshot/report.py` / 비수렴 실패를 `human_decision_required`로 분기

### 폐기

- **T-13 프리필터 대소문자 버그 수정 제안 (C3a)** — REFUTED: **이미 main에서 수정됨**.
  `hooks/enforcement/kompound-snapshot-gate.sh:50-62`가 `case`를 `shopt -s nocasematch`로
  감싸고 인라인 주석이 해당 LEARNING 엔트리를 인용한다. 이미 고쳐진 결함을 protected 스크립트
  수정 제안으로 올리면 사람 승인 사이클을 낭비한다 — 게이트가 정확히 이걸 잡았다.
- `sdd-orchestration` (2신호) — 병렬 worktree `git add -A` / 브랜치 전환 금지.
  이미 `CLAUDE.md` "핵심 규칙"에 반영돼 있어 **중복**으로 폐기.
- `sdd-tdd` (1신호) — 거대 레포 build-aware TDD. 1회성·맥락 한정(레포 특화 빌드 프로파일)이라
  행동 규칙 변경에서 강등.
- `harness` (1신호) — CLAUDE.md 부재 시 `CLAUDE.local.md` 폴백. 이번 회고가 **그 규칙을 실제로
  실행**했으므로(위 적용 2번째 항목) 별도 규칙화 불필요.
- `two-stage-prefilter-parity` 중 arch 리뷰 항목은 제안으로 살아남았고, 그 원인이 된 코드 결함은
  위 C3a로 폐기 — 클러스터가 절반만 생존.
