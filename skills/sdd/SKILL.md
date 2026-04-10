---
name: sdd
description: "Use when a user mentions a feature idea, requirement, or spec document, or asks to implement something new — even if described informally or briefly"
---

# SDD (Spec-Driven Development)

기능 아이디어를 **Spec → Develop → Plan → Execute** 4단계로 구조화하여 구현하는 워크플로우.
sdd는 **순수 팀장**이다. 직접 문서를 작성하지 않고, 관리/보고/승인/에스컬레이션만 담당한다.

**핵심 원칙:** 문서가 곧 상태. 문서 존재 여부 + checkbox + 라벨로 Phase를 추적한다.

<HARD-GATE>
1. Phase 순서를 건너뛰지 않는다. blocker-checker 통과 + 사용자 승인 없이 Phase 2로, develop 승인 없이 Phase 3으로 진입하지 않는다.
2. TDD Iron Law — FULL 태스크: RED 먼저, 구현자는 테스트 파일 수정 금지, GREEN 필수, 리뷰 필수.
3. Phase 4 격리: 모든 구현은 worktree 안에서 수행. main 브랜치 직접 수정 금지.
4. Adversarial Escalation: 이터레이션 3회 소진 시 adversarial-review 호출. BLOCKED이면 worktree 폐기.
5. 의존 태스크 순서: 의존 태스크가 DONE이 아니면 시작 금지.
6. Phase 3(Plan) 없이 Phase 4(Execute) 진입 금지. task 문서 + DAG/Wave + 사용자 승인 필수.
</HARD-GATE>

## Red Flags

| 합리화 | 현실 |
|--------|------|
| "스펙이 짧으니 검사 생략" | 짧은 스펙일수록 누락이 많다 |
| "develop 없이 바로 태스크" | 설계 없는 구현은 재작업을 낳는다 |
| "이슈 1개니 그냥 진행" | 이슈 1개도 반드시 사용자 확인 |
| "간단한 변경이라 worktree 불필요" | 모든 Phase 4 작업은 격리 필수 |
| "테스트를 살짝 수정하면 통과" | implementer는 테스트 코드 수정 금지 |
| "Plan 없이 바로 구현" | task + DAG + 승인 없이 Execute 진입 금지 |

## 문서 구조

```
docs/sdd/
├── spec/{YYYY-MM-DD}-{feature}.md
├── design/                              # [FULL 모드 전용]
│   ├── ui/{YYYY-MM-DD}-{feature}.md
│   ├── api/{YYYY-MM-DD}-{feature}.md
│   └── review/{YYYY-MM-DD}-{feature}.md
├── context/{YYYY-MM-DD}-{feature}.md    # [FULL 모드]
├── develop/{YYYY-MM-DD}-{feature}.md
├── task/{feature}/{YYYY-MM-DD}-{task}.md
└── result/{YYYY-MM-DD}-{feature}.md
```

파일명: `{YYYY-MM-DD}-{feature-name}.md` (kebab-case, 영문).

## Phase 판정 규칙 (세션 재개 시)

**정밀 모드**: context 문서의 `## 라벨 상태`에서 현재 라벨을 읽어 판정.

**호환 모드** (context 없음): spec 없음 → P1 미시작 / spec만 → P2 미시작 / develop만 → P3 미시작 / task + ORCHESTRATOR_STATE 없음 → P3 진행 중 / ORCHESTRATOR_STATE 있음 + 미완료 → P4 진행 중 / 전체 완료 + result 없음 → P4 대기 / result 있음 → 완료

## 라벨 기반 상태 머신

```
PHASE1_UX_RESEARCH_DONE → PHASE1_SPEC_DRAFT → PHASE1_BLOCKER_CHECK_PASS → PHASE1_USER_APPROVED
→ PHASE2_START → PHASE2_API_DESIGN_COMPLETE → PHASE2_ARCH_REVIEW_PASS → PHASE2_DEVELOP_INTEGRATED → PHASE2_USER_APPROVED
→ PHASE3_PLAN_START → PHASE3_TASKMASTER_DONE → PHASE3_DAG_CONSTRUCTED → PHASE3_USER_APPROVED
→ PHASE4_WORKTREE_CREATED → PHASE4_TASK_{N}_TEST_RED → PHASE4_TASK_{N}_IMPLEMENTING → PHASE4_TASK_{N}_REVIEWING
→ PHASE4_TASK_{N}_GREEN → PHASE4_TASK_{N}_VERIFIED → PHASE4_TASK_{N}_REFACTOR_TESTED → PHASE4_TASK_{N}_DONE
→ PHASE4_ALL_TASKS_DONE → PHASE4_INTEGRATION_TEST_PASS → PHASE4_RESULT_GENERATED → PHASE4_MERGED
```

라벨은 **전진만 가능**. 스펙 변경 정책에서만 롤백 허용.

## 에이전트 출력 표준

| 상태 | 의미 | 컨트롤러 행동 |
|------|------|--------------|
| `DONE` | 완료 | 다음 단계 |
| `DONE_WITH_CONCERNS` | 완료+우려 | 검토 후 결정 |
| `NEEDS_CONTEXT` | 정보 부족 | 컨텍스트 보충 후 재파견 |
| `BLOCKED` | 근본 문제 | 에스컬레이션 |

재시도 한계: **최대 3회**. 초과 시 사용자 에스컬레이션.

## 에이전트 목록

| 모델 | 용도 | 비용 |
|------|------|------|
| **opus** | 아키텍처 결정, 설계 판단 | 10x |
| **sonnet** | 구현, 리뷰, 테스트 (90%) | 3x |
| **haiku** | 패턴 매칭, 단순 판단 | 1x |

| 에이전트 | Phase | 모델 | 역할 |
|---------|-------|------|------|
| `sdd-ux-researcher` | 1 | sonnet | 사용자 요구사항 분석, 기능 매핑 |
| `sdd-product-designer` | 1 | sonnet | spec 초안 작성 |
| `sdd-ui-designer` | 1 | opus | UI/UX 명세 |
| `sdd-blocker-checker` | 1 | haiku | spec 블로커 탐지 |
| `sdd-context-manager` | 전체 | haiku | 공유 상태 관리 |
| `webapp-architect` | 2 | opus | 웹 앱 아키텍처 결정, develop 작성 |
| `flutter-architect` | 2 | opus | Flutter 앱 아키텍처 결정, develop 작성 |
| `native-architect` | 2 | opus | Rust/C++ 네이티브 아키텍처 결정, develop 작성 |
| `sdd-api-designer` | 2 | opus | API 계약 정의 |
| `sdd-architect-reviewer` | 2 | opus | 설계 정합성 검증 |
| `sdd-taskmaster` | 3 | haiku | spec+develop에서 태스크 도출 |
| `sdd-implementer` | 4 | sonnet | 범용 구현 |
| `sdd-ts-engineer` | 4 | sonnet | TypeScript/Node.js |
| `sdd-rust-engineer` | 4 | sonnet | Rust 백엔드 |
| `sdd-react-specialist` | 4 | sonnet | React 프론트엔드 |
| `sdd-nextjs-engineer` | 4 | sonnet | Next.js 풀스택 |
| `sdd-vue-engineer` | 4 | sonnet | Vue 3/Nuxt 3 |
| `sdd-swift-engineer` | 4 | sonnet | Swift/iOS/macOS |
| `sdd-cpp-engineer` | 4 | sonnet | C++20/23 |
| `sdd-flutter-engineer` | 4 | sonnet | Flutter/Dart |
| `sdd-fastapi-engineer` | 4 | sonnet | FastAPI/Python API |
| `sdd-python-engineer` | 4 | sonnet | Python 일반 |
| `sdd-sql-engineer` | 4 | sonnet | SQL/DB 스키마 |
| `sdd-compliance-checker` | 4 | haiku | 스펙 준수 검증 |
| `sdd-reviewer` | 4 | sonnet | 코드 품질 [P1] 리뷰 |
| `sdd-performance-engineer` | 4 | sonnet | 성능 [P2] 검증 |
| `sdd-test-automator` | 4 | sonnet | TDD(tdd/verify/refactor) |
| `adversarial-reviewer` | 4 | opus | 3회 소진 후 접근법 비판 |

---

## Phase 1: Spec

sdd는 직접 spec을 작성하지 않는다. 에이전트에 위임한다.

### 프로세스

1. 기존 spec 확인 (`docs/sdd/spec/` 스캔)
2. `sdd-ux-researcher` → 사용자 요구사항 분석 + 기능 매핑
3. `sdd-product-designer` → spec 초안 작성
4. `sdd-ui-designer` → UI/UX 명세 (백엔드 전용이면 생략)
5. spec 저장 → `sdd-blocker-checker` 디스패치
6. 블로커 있으면 수정→재검사, 없으면 사용자 승인 게이트

### spec 템플릿

```markdown
# {feature} Spec

## 개요
- 한줄 요약:
- 타겟 사용자:
- 핵심 가치:

## 사용자 요구사항 (원문)
| # | 사용자 요구 | → 기능 |
|---|------------|--------|
| 1 | "원문 그대로" | F1, F2 |

## 기능 요구사항
### F1: {기능명}
- WHEN [조건] THE SYSTEM SHALL [동작]
- Acceptance: [검증 조건]

## 용어 정의
```

---

## Phase 2: Develop

sdd는 직접 develop을 작성하지 않는다. [webapp/flutter/native]-architect + api-designer + architect-reviewer 협업.
develop = 아키텍처 결정, 폴더 구조, 데이터 모델, API 설계, 테스트 전략. **태스크 목록 없음** (Phase 3에서 도출).

### 설계 모드 판정

| 조건 | 모드 |
|------|------|
| 기능 요구사항 3개 이하 + API/UI 미언급 | SIMPLE |
| API/UI 키워드 존재, 또는 프론트+백엔드 혼합 | FULL |
| 사용자 명시 요청 | 해당 모드 |

### Architect 선택 기준

프로젝트 파일 → spec 키워드 순서로 판정한다.

| 신호 | Architect |
|------|-----------|
| `pubspec.yaml` 존재 / spec에 Flutter·Dart 언급 | `flutter-architect` |
| `Cargo.toml` / `CMakeLists.txt` 존재 / spec에 Rust·C++ 언급 | `native-architect` |
| `package.json` 존재 / spec에 React·Vue·Next·웹 언급 | `webapp-architect` |
| 판정 불가 | 사용자에게 확인 후 dispatch |

### SIMPLE 모드

1. 컨텍스트 탐색 → Architect 선택 기준으로 프로젝트 타입 판정 → 해당 architect 디스패치 (develop 작성)
2. `sdd-architect-reviewer` 디스패치 (평가) → Critical이면 수정 후 재평가
3. 사용자 승인 게이트

### FULL 모드

```
1. context-manager INIT → PHASE2_START
2. sdd-api-designer → design/api/ → PHASE2_API_DESIGN_COMPLETE
3. [사용자 중간 확인] API 설계 피드백
4. sdd-architect-reviewer → design/review/ → PHASE2_ARCH_REVIEW_PASS
5. [Architect 선택 기준으로 판정한 architect] → develop 통합 생성 (제약사항 포함) → PHASE2_DEVELOP_INTEGRATED
6. sdd-architect-reviewer → develop 평가 → PHASE2_DEVELOP_REVIEW_PASS
7. [사용자 최종 승인] → PHASE2_USER_APPROVED
```

UI 명세는 Phase 1에서 이미 완성. 순서: UI(P1) → API → Review → develop 통합.

### TDD 적용 판정

| 레이어 | TDD | 근거 |
|--------|-----|------|
| Model/Service | FULL | 순수 로직, 단위 테스트 용이 |
| ViewModel/Controller | FULL | 상태 전이, mock 격리 가능 |
| View/UI | SKIP | 통합 테스트로 대체 |
| 설정/스캐폴딩 | SKIP | 테스트 불필요 |
| DB 스키마/마이그레이션 | FULL | 데이터 무결성 필수 |

### develop 템플릿

```markdown
# {Feature Name} — 기술 설계

## 관련 spec
## 설계 산출물 참조 (FULL 모드)
## 아키텍처 결정
## 제약사항
비기능 요구사항, 성능, 보안, 접근성, 기술 스택 제한 등.
## 폴더 구조
(NEW)/(MODIFY) 표기. architecture-rules.json 준수 확인.
## API 설계
## 데이터 모델
## 테스트 전략
- 테스트 프레임워크 / 커버리지 전략
- 단위 테스트 대상 (TDD FULL) / 통합 테스트 대상 (verify)
- 성능 테스트 전략 / 성능 안티패턴 감시
- View/UI 검증: compliance-checker + reviewer + test-automator(verify)
```

---

## Phase 3: Plan

spec + develop에서 태스크를 도출하고 실행 계획을 수립한다. sdd 리드는 직접 수행하지 않고 `sdd-taskmaster`에 위임한다.

### 프로세스

```
1. sdd-taskmaster 디스패치 (모드: tasks)
   - 입력: spec + develop 전문 + worktree 경로
   - 배치 크기: 최대 5개 (태스크 수에 따라 순차 배치)
   - 각 태스크마다 task 문서 생성 (sdd-taskrunner 참고 문서의 기준 사용)
   → PHASE3_TASKMASTER_DONE

2. sdd-taskmaster 디스패치 (모드: dag)
   - 입력: 생성된 task 문서 목록
   - 의존 관계 분석 → DAG → Wave 자동 구성
   - ORCHESTRATOR_STATE.md 초기 생성 (상태: PLANNING)
   → PHASE3_DAG_CONSTRUCTED

3. [사용자 승인 게이트]
   task 목록 + DAG/Wave + 구현자 배정 제시 → 승인
   → PHASE3_USER_APPROVED
```

> **ORCHESTRATOR_STATE.md 스키마**: [skills/sdd-orchestrator/references/state-schema.md](../sdd-orchestrator/references/state-schema.md) (SOT)

### task 템플릿

```markdown
# T-{N}: {Task Name}

## 관련 문서 (spec, develop 경로)
## 구현자 / TDD 수준 (FULL|SKIP + 사유)
## 완료 조건 (checkbox)
## 테스트 시나리오 (TDD FULL: 시나리오/입력/기대결과/유형 테이블)
## 의존 태스크
## 예상 변경 파일
## Steps (checkbox)
## 검증 명령어
```

---

## Phase 4: Execute

**Phase 4는 sdd 리드가 직접 실행하지 않는다.** `sdd-orchestrator` 스킬이 전담한다.

### 진입

1. `EnterWorktree` → `git branch -m feat/{feature-name}` → 스냅샷 커밋
   → PHASE4_WORKTREE_CREATED
2. `Skill(sdd-orchestrator)` 호출 — ORCHESTRATOR_STATE.md 경로를 인자로 전달

sdd 리드는 오케스트레이터 실행 결과만 수신한다. 리뷰 루프, 테스트 루프, 구현자 선택, 병렬 실행 규칙, 심각도 체계, 통합 검증, result 생성, 머지까지 **전부 오케스트레이터가 담당**한다.

> **상세 절차**: [skills/sdd-orchestrator/SKILL.md](../sdd-orchestrator/SKILL.md)
> **상태 스키마**: [skills/sdd-orchestrator/references/state-schema.md](../sdd-orchestrator/references/state-schema.md)
> **디스패치 가이드**: [skills/sdd-orchestrator/references/agent-dispatch-guide.md](../sdd-orchestrator/references/agent-dispatch-guide.md)

### 리드의 책임

- Phase 4 진입 시 worktree 생성 + 오케스트레이터 호출
- 오케스트레이터가 에스컬레이션(`escalated`, `PAUSED_AT_LIMIT`, 빌드 실패)을 보고하면 사용자에게 중계
- 오케스트레이터가 완료를 보고하면 사용자에게 머지 승인 요청
- **직접 Engineer/Reviewer/Test Automator를 디스패치하지 않는다** — 오케스트레이터가 담당

### 심각도 체계 (SOT)

| 심각도 | 범위 | 판정 주체 |
|--------|------|----------|
| `[P1]` | 기능 오류, 아키텍처 위반 | sdd-reviewer — **반드시 수정** |
| `[P2]` | 실측 성능 문제 | sdd-performance-engineer — **반드시 수정** |
| `[P3]` | 스타일, 네이밍 | 린터/포매터 위임 |

> **상세 판정 기준**: [P1]은 `agents/sdd-reviewer.md`, [P2]는 `agents/sdd-performance-engineer.md` 참조.

---

## 게이트 정책

| 전환 | 게이트 |
|------|--------|
| Phase 1 → 2 | blocker-checker + 사용자 승인 |
| Phase 2 모드 | SIMPLE/FULL 사용자 확인 |
| Phase 2 → 3 | develop + 사용자 승인 |
| Phase 3 → 4 | task + DAG/Wave + 사용자 승인 |
| Phase 4 내부 루프 | `sdd-orchestrator`가 담당 (RED/GREEN/VERIFY 게이트 전부) |
| Phase 4 완료 | 통합 테스트 → result → 사용자 확인 → 머지 |
| 중단 | 현재 태스크 완료 → result → 머지 |

## CLAUDE.md 규칙 매핑

| 규칙 | 적용 시점 |
|------|----------|
| 스냅샷 커밋 | Phase 4 worktree 생성 직후 |
| 서브태스크별 커밋 | 구현자 각 스텝 완료 시 |
| 브랜치 원칙 | Phase 4 EnterWorktree + branch rename |

## 스펙 변경 정책

Phase 4 도중: 현재 태스크 완료 → spec v2 수정 → blocker-checker 재실행 → (FULL) design 영향 분석 → develop 수정 → 승인 → Phase 4 재개.

## 멀티 feature / 하위 호환성

- 각 feature는 독립 worktree + 독립 문서. 동시 진행 가능.
- SIMPLE 모드가 기본. context/design 없으면 호환 모드 폴백. 마이그레이션 불필요.
