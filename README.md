# Moon Harness

아이디어에서 배포까지, AI 에이전트의 전체 개발 라이프사이클을 구조화하는 Claude Code 플러그인.

## 설치

### 방법 1: CLI로 설치

```bash
/plugin install moon-harness@moon-harness
```

### 방법 2: `settings.json` 직접 편집

`~/.claude/settings.json`에 추가:

```json
{
  "extraKnownMarketplaces": {
    "moon-harness": {
      "source": {
        "source": "github",
        "repo": "moonseokchoi-kr/moon-harness"
      }
    }
  },
  "enabledPlugins": {
    "moon-harness@moon-harness": true
  }
}
```

Claude Code 재시작 후 모든 스킬, 에이전트, 훅이 자동 활성화된다.

---

## 파이프라인

```
아이디어                       구현                   배포
──────────────────────    ──────────────    ──────────────────────
idea-workshop              SDD Phase 1       Phase 4-1: Review
  Phase 1: 발산               ↓                 ↓
  Phase 2: 리프레이밍          Phase 2 → 3       Phase 4-2: Ship
  Phase 3A: 팀 리서치                            ↓
  Phase 3B: 냉철 검증                            Phase 4-3: Verify
  Phase 3C: PRD 작성
  (Phase 2 ↔ 3B 이터레이션)
```

### 아이디어 단계

| 스킬 | 역할 |
|------|------|
| `/idea-workshop` | 아이디어 전체 라이프사이클 통합 (발산 → 리프레이밍 → 팀 리서치 → 냉철 검증 → PRD) |

Phase 3A에서 **기획팀 Agent Team** (market/user/feasibility/biz-model researcher + reviewer) 이 병렬 리서치를 수행하고, Phase 3B에서 리서치 실증 데이터를 근거로 냉철 대화 검증, Phase 3C에서 리뷰어가 품질 게이트 통과 후 `docs/PRD.md` 작성.

### 구현 단계

| 스킬 | 역할 |
|------|------|
| `/spec-design` | 자동 파이프라인 기반 Spec-Driven Development |
| `/adversarial-review` | 리뷰 3회 실패 시 에스컬레이션 |
| `/git-worktree` | 격리된 feature 브랜치 |

### 환경 관리

| 스킬 | 역할 |
|------|------|
| `/harness` | 프로젝트 환경 구성 + 훅 설치 |
| `/harness audit` | 12원칙 기반 하네스 건강도 점검 (L1~L5) |
| `/handoff` | 세션 컨텍스트 보존 |

---

## 자동 파이프라인 (spec-design)

`/spec-design start <feature>` 한 번으로 Phase 4 진입까지 자동 진행.

- **Stop 훅 컨트롤러** (`stop-pipeline.py`) 가 각 Phase 전환을 자동 관리
- 16개 라벨 기반 상태 머신
- 사용자 게이트(spec/arch/ui/api/design/plan) 에서만 정지
- Circuit breaker (5분 TTL, 20회) 로 무한 루프 방지
- Session 격리 + Stale state 자동 정리

---

## Enforcement 훅

스킬 지시가 아닌 훅으로 물리적으로 행동을 강제한다:

| 훅 | 이벤트 | 역할 |
|----|--------|------|
| `role-gate` | PreToolUse Edit\|Write | 오케스트레이터 코드 직접 편집 차단 |
| `tdd-gate` | PreToolUse Edit | 구현자 테스트 파일 수정 차단 |
| `branch-gate` | PreToolUse Bash | Phase 4 중 main 브랜치 커밋 차단 |
| `e2e-gate` | PreToolUse Bash | git commit 시 E2E 파일 누락 차단 |
| `phase-gate` | SessionStart | Phase 선행조건 진단 |
| `harness-check` | SessionStart | 하네스 미설정 프로젝트 경고 |
| `escalation-tracker` | PostToolUse Agent | 3회 BLOCKED 자동 에스컬레이션 |
| `stop-pipeline` | Stop | spec-design 파이프라인 자동 진행 |

보안 훅 (secret-detect, dangerous-command, sensitive-file)도 함께 포함.

---

## 실수 학습 시스템

AI가 실수하면 자동으로 기록하고, 다음 세션에서 반복하지 않는다.

```
Layer 1: CLAUDE.md — 포인터 ("pitfalls는 docs/pitfalls.md 참고")
Layer 2: docs/pitfalls.md + docs/lessons-learned.md — 전체 기록
Layer 3: 훅 — 세션 종료 시 자동 추출 + 관련 작업 시 선택적 주입
```

같은 실수 3회 이상 → CLAUDE.md 핵심 규칙으로 승격.

---

## 설계 철학

> "더 적게 만들되 더 단단하게"

- 하드 게이트 (advisory 리뷰가 아닌)
- 기계적 강제 (텍스트 지시가 아닌)
- 파이프라인 자동화 (매번 수동 트리거가 아닌)

---

## 개발

로컬에서 플러그인 개발 시:

```bash
git clone https://github.com/moonseokchoi-kr/moon-harness
cd moon-harness
claude --plugin-dir .
# /reload-plugins 로 변경사항 실시간 반영
```

---

## License

MIT
