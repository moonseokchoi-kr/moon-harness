---
name: sdd
description: "Use when a user mentions a feature idea, requirement, or spec document, or asks to implement something new — even if described informally or briefly"
---

# SDD (Spec-Driven Development)

기능 아이디어를 **Spec → Develop → Plan → Execute** 4단계로 구조화하여 구현하는 워크플로우.
sdd는 **순수 팀장**이다. 직접 문서를 작성하지 않고, 관리/보고/승인/에스컬레이션만 담당한다.

**핵심 원칙:** 문서가 곧 상태. 문서 존재 여부 + checkbox + 라벨로 Phase를 추적한다.

<HARD-GATE>
1. Phase 순서를 건너뛰지 않는다. Phase N 진입 시점에 **직전 Phase 산출물 완전성**을 필수 검증하고, 불완전하면 직전 Phase로 롤백하여 누락 산출물을 먼저 복원한 뒤 재진입한다. blocker-checker 통과 + 사용자 승인 없이 Phase 2로, develop 승인 없이 Phase 3으로 진입하지 않는다.
2. TDD Iron Law — FULL 태스크: RED 먼저, 구현자는 테스트 파일 수정 금지, GREEN 필수, 리뷰 필수.
3. Phase 4 격리: 모든 구현은 worktree 안에서 수행. main 브랜치 직접 수정 금지.
4. Adversarial Escalation: 이터레이션 3회 소진 시 adversarial-review 호출. BLOCKED이면 worktree 폐기.
5. 의존 태스크 순서: 의존 태스크가 DONE이 아니면 시작 금지.
6. Phase 3(Plan) 없이 Phase 4(Execute) 진입 금지. task 문서 + DAG/Wave + 사용자 승인 필수.
</HARD-GATE>

## Anti-Patterns (HARD-GATE 위반 트리거)

아래 합리화가 감지되면 즉시 중단하고 올바른 절차로 돌아간다.

| 합리화 | 실제 결과 | 올바른 행동 |
|--------|----------|------------|
| "스펙이 짧으니 검사 생략" | 짧은 스펙일수록 누락이 많다 | blocker-checker 실행 |
| "설계 없이 바로 태스크" | 설계 없는 구현은 재작업을 낳는다 | Phase 2 설계 먼저 |
| "이슈 1개니 그냥 진행" | 이슈 1개도 쌓이면 P1 | 사용자 확인 후 진행 |
| "간단한 변경이라 worktree 불필요" | 격리 없으면 main 오염 | Phase 4 시작 시 worktree 필수 |
| "테스트를 살짝 수정하면 통과" | TDD 무결성 파괴 | 테스트 파일 수정 금지, 구현으로 통과 |
| "Plan 없이 바로 구현" | 방향 없는 구현 | task + DAG + 승인 후 진입 |

## 문서 구조

```
docs/sdd/
├── spec/{YYYY-MM-DD}-{feature}.md
├── design/                              # Phase 2 설계
│   ├── arch/{YYYY-MM-DD}-{feature}.md   # 아키텍처 (모든 모드)
│   ├── ui/{YYYY-MM-DD}-{feature}.md     # UI/UX 명세 (FULL 모드)
│   └── api/{YYYY-MM-DD}-{feature}.md    # API 계약 (FULL 모드)
├── context/{YYYY-MM-DD}-{feature}.md    # 공유 상태 (FULL 모드)
├── task/{feature}/{YYYY-MM-DD}-T-{N}-{task}.md  # Phase 3 태스크
├── ORCHESTRATOR_STATE.md                 # Phase 4 상태 추적
└── result/{YYYY-MM-DD}-{feature}.md     # Phase 4 최종 결과
```

파일명: `{YYYY-MM-DD}-{feature-name}.md` (kebab-case, 영문).

## Phase 판정 규칙 (세션 재개 시)

**정밀 모드**: context 문서의 `## 라벨 상태`에서 현재 라벨을 읽어 판정.

**호환 모드** (context 없음) — 직전 Phase 산출물이 **완전할 때만** 다음 Phase로 진입 가능하다고 판정한다:

| 관찰 상태 | 판정 | 비고 |
|----------|------|------|
| spec 없음 | P1 미시작 | — |
| spec 있음 + design/arch 없음 | **P2 미시작** | Phase 1 완료 |
| Phase 1 완료 + design/arch 있음 | P2 진행 중 | ui-designer/api-designer 진행 |
| Phase 1 완료 + design/arch 있음 + (FULL 모드인데 design/ui 또는 design/api 누락) | **P2 미완** | → 누락분 복원 |
| Phase 2 완료 + task 문서 없음 | P3 미시작 | — |
| Phase 2 완료 + task 있음 + ORCHESTRATOR_STATE 없음 | P3 진행 중 | taskmaster dag 모드 미수행 |
| Phase 3 완료 + ORCHESTRATOR_STATE 있음 + 미완료 | P4 진행 중 | — |
| Phase 4 완료 + result 없음 | P4 대기 | — |
| result 있음 | 완료 | — |

**핵심 원칙**: "직전 Phase의 **모든** 필수 산출물이 존재하지 않으면 다음 Phase로 진입하지 않는다." 불완전 감지 시 해당 Phase로 롤백해서 누락분만 복원한다.

## 라벨 기반 상태 머신

```
PHASE1_UX_RESEARCH_DONE → PHASE1_SPEC_DRAFT → PHASE1_BLOCKER_CHECK_PASS → PHASE1_USER_APPROVED
→ PHASE2_START → PHASE2_ARCH_STRUCTURE_DONE → PHASE2_ARCH_USER_APPROVED → PHASE2_UI_DESIGN_COMPLETE 
→ PHASE2_API_DESIGN_COMPLETE → PHASE2_DESIGN_USER_APPROVED → PHASE2_USER_APPROVED
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

### 에이전트 파일 생성 실패 처리

에이전트가 `DONE` 보고했지만 기대 파일이 존재하지 않는 경우:
1. **리드가 직접 Write/Edit로 파일을 대신 생성하지 않는다** — `orchestrator-no-direct-edit` 규칙
2. **해당 에이전트를 재디스패치한다** (최대 3회) — "파일이 생성되지 않았다. Write 툴로 {경로}에 직접 저장하라"를 프롬프트에 명시
3. 3회 재디스패치 후에도 실패 시 사용자 에스컬레이션

## 에이전트 목록

| 모델 | 용도 | 비용 |
|------|------|------|
| **opus** | 아키텍처 결정, 설계 판단 | 10x |
| **sonnet** | 구현, 리뷰, 테스트 (90%) | 3x |
| **haiku** | 패턴 매칭, 단순 판단 | 1x |

| 에이전트 | Phase | 모델 | 역할 |
|---------|-------|------|------|
| `sdd-ux-researcher` | 1 | sonnet | 사용자 요구사항 분석 + spec 작성 |
| `sdd-ui-designer` | 2 | opus | UI/UX 명세 |
| `sdd-blocker-checker` | 1 | haiku | spec 블로커 탐지 |
| `sdd-context-manager` | 전체 | haiku | 공유 상태 관리 |
| `webapp-architect` | 2 | opus | 웹 앱 아키텍처 결정, develop 작성 |
| `flutter-architect` | 2 | opus | Flutter 앱 아키텍처 결정, develop 작성 |
| `native-architect` | 2 | opus | Rust/C++ 네이티브 아키텍처 결정, develop 작성 |
| `sdd-api-designer` | 2 | opus | API 계약 정의 |
| `sdd-architect-reviewer` | 2 | opus | 설계 정합성 검증 |
| `sdd-taskmaster` | 3 | sonnet | spec+develop에서 태스크 도출 |
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
| `sdd-compliance-checker` | 4 | sonnet | 스펙 준수 검증 |
| `sdd-reviewer` | 4 | sonnet | 코드 품질 [P1] 리뷰 |
| `sdd-performance-engineer` | 4 | sonnet | 성능 [P2] 검증 |
| `sdd-test-automator` | 4 | sonnet | TDD(tdd/verify/refactor) |
| `adversarial-reviewer` | 4 | opus | 3회 소진 후 접근법 비판 |

---

## Phase 1: Spec

sdd는 직접 spec을 작성하지 않는다. 에이전트에 위임한다.

### 프로세스

1. 기존 spec 확인 (`docs/sdd/spec/` 스캔)
2. `sdd-ux-researcher` → 사용자 요구사항 분석 + spec 작성 (플랫폼/스택 명시 포함)
3. `sdd-blocker-checker` 1차 디스패치 → 플랫폼/스택 미확정 여부 우선 확인
   - BLOCKED(플랫폼/스택 미확정) → 사용자 확인 후 spec 보완 → 재검사
4. spec 저장 → `sdd-blocker-checker` 2차 디스패치 (전체 블로커 검사)
5. 블로커 있으면 수정→재검사, 없으면 사용자 승인 게이트

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

## Phase 2: Design

sdd는 직접 설계를 작성하지 않는다. [webapp/flutter/native]-architect + ui-designer + api-designer + architect-reviewer 협업.
설계 산출물 = 아키텍처(arch), 사용자 인터페이스(ui), API 계약(api). **태스크 목록 없음** (Phase 3에서 도출).

### Phase 2 진입: worktree 격리 (필수)

Phase 2 프로세스 시작 전에 worktree를 생성한다. 이후 **Phase 2, 3, 4의 모든 작업은 worktree 내에서 수행**한다.

1. `Skill(git-worktree, {feature-name})` 호출 — `./worktrees/{feature-name}` 경로에 worktree + `feat/{feature-name}` 브랜치 생성
2. 이후 모든 에이전트 디스패치 시 **worktree 절대 경로**를 프롬프트에 반드시 주입한다
3. `.gitignore`에 `worktrees/` 포함 확인 (없으면 추가)
4. worktree 경로 예시: `/Users/moon/Workspace/money_track/worktrees/money-track-mvp`

→ PHASE2_WORKTREE_CREATED

> **중요:** 에이전트가 파일을 생성할 때 메인 경로가 아닌 **worktree 경로** 아래에 저장해야 한다. 리드는 디스패치 프롬프트에 worktree 절대 경로를 항상 포함하고, "이 경로 아래에 파일을 저장하라"고 명시한다.

### Phase 2 진입 전 검증 (필수)

Phase 2 프로세스를 시작하기 **전에** 아래 체크리스트를 먼저 기계적으로 검증한다. 하나라도 실패하면 Phase 2 진입 금지 — 해당 조치를 먼저 수행한다.

| # | 체크 | 실패 시 조치 |
|---|------|------|
| 1 | `docs/sdd/spec/{YYYY-MM-DD}-{feature}.md` 존재 | **Phase 1로 롤백** — `sdd-ux-researcher` 디스패치 |
| 2 | spec 말미에 blocker-check PASS 마크 또는 이전 세션 승인 기록 | `sdd-blocker-checker` 재실행 |
| 3 | Phase 1 사용자 승인 게이트 통과 기록 | 사용자 승인 요청 |
| 4 | worktree 생성 완료 (Phase 2 진입과 동시) | `Skill(git-worktree)` 호출 |

검증 통과 후에만 아래 "설계 모드 판정"으로 진입한다.

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

### FULL 모드 (순차)

```
1. [Architect 선택 기준으로 판정한 architect] → 아키텍처 설계
   (레이어 구조, 폴더 구조, 컴포넌트 경계, 기술 제약사항, 테스트 전략)
   → design/arch/ 저장
   → sdd-architect-reviewer 리뷰 → 수정 → 재리뷰 (PASS까지 반복)
   → PHASE2_ARCH_STRUCTURE_DONE

2. [사용자 아키텍처 승인 게이트]
   아키텍처 구조 요약 제시 → 사용자 확인
   피드백 있으면 architect 재디스패치 후 재검토
   → PHASE2_ARCH_USER_APPROVED

3. sdd-ui-designer → 순수 UX 명세 (아키텍처 제약 안에서)
   → design/ui/ 저장
   ※ 작성 범위: 화면 레이아웃, 플로우, 인터랙션, 비주얼 가이드
   ※ 작성 금지: 상태 타입/관리 위치, API 엔드포인트, 프레임워크 API 명칭
   → sdd-architect-reviewer → UI 명세 리뷰 → 수정 → PASS
   → [사용자 UI 피드백] → 반영
   → PHASE2_UI_DESIGN_COMPLETE

4. sdd-api-designer (UI 명세 필수 입력) → UI 명세에서 도출된 데이터 요구사항 + arch 기반 API/데이터 계약 설계
   ※ UI 설계 중 발견된 데이터 요구사항이 API 범위를 결정함 — ui-designer 완료 후 진행
   → design/api/ 저장
   → sdd-architect-reviewer → API 명세 리뷰 → 수정 → PASS
   → [사용자 API 피드백] → 반영
   → PHASE2_API_DESIGN_COMPLETE

5. [사용자 최종 설계 승인] → PHASE2_DESIGN_USER_APPROVED
   
6. sdd-context-manager (FULL 모드) → context 문서 초기 생성
   → PHASE2_USER_APPROVED
```

### 모든 레이어에 테스트

모든 레이어는 테스트를 먼저 작성한다 (RED → GREEN). 차이는 테스트 타입뿐이다.

| 레이어 | 테스트 타입 | 시점 |
|--------|-----------|------|
| Model/Service/Domain | 단위 테스트 | 구현 전 RED |
| ViewModel/Controller | 단위 테스트 | 구현 전 RED |
| View/UI | 통합/E2E 테스트 (Maestro, Playwright 등) | 구현 전 RED |
| Platform Channel | E2E 테스트 | 구현 전 RED |
| DB 스키마/마이그레이션 | 단위 테스트 | 구현 전 RED |
| 설정/스캐폴딩 | 검증 테스트 (프레임워크별) | 구현 전 또는 후 |

### 아키텍처 문서 템플릿

아키텍처 문서(`docs/sdd/design/arch/{YYYY-MM-DD}-{feature}.md`)는 architect가 작성한다.

```markdown
# {Feature Name} — 아키텍처

## 레이어 구조
(Presentation / Domain / Data / Platform 등)

## 폴더 구조
모듈/기능 단위 디렉토리 경계만 정의한다. 특정 파일명은 엔지니어가 결정.

예시:
```
lib/
├── features/     ← 기능별 모듈
│   ├── home/
│   ├── transaction/
│   └── settings/
├── core/         ← 공통 레이어
└── shared/       ← 공유 컴포넌트
```
(파일명 수준 X — `home_screen.dart` 같은 구체적 파일명 기입 금지)

## 컴포넌트 경계
주요 컴포넌트와 책임 범위

## 기술 스택 & 제약사항
비기능 요구사항, 성능, 보안, 기술 스택 제한 등

## 테스트 전략
구체적 시나리오는 작성하지 않는다 — test-automator가 레이어 타입 기반으로 도출.

- **레이어별 테스트 타입**:
  | 레이어 | 테스트 타입 | 프레임워크 |
  |--------|-----------|-----------|
  | Domain/Service | 단위 테스트 | (예: flutter_test, jest) |
  | View/UI | E2E/통합 | (예: Maestro, Playwright) |
  | Platform Channel | E2E | (예: integration_test) |
  | 설정/스캐폴딩 | — | — |
- **E2E 검증 경계**: (어떤 사용자 시나리오를 E2E로 검증하는가)
```

---

## Phase 3: Plan

spec + 설계 문서(arch/ui/api)에서 태스크를 도출하고 실행 계획을 수립한다. sdd 리드는 직접 수행하지 않고 `sdd-taskmaster`에 위임한다.

### 진입 전 검증 (필수)

| # | 체크 | 실패 시 조치 |
|---|------|------|
| 1 | Phase 2 진입 전 검증 전부 통과 | **Phase 2 진입 전 검증으로 되돌아가기** |
| 2 | `docs/sdd/design/arch/{YYYY-MM-DD}-{feature}.md` 존재 | **Phase 2로 롤백** — architect 재디스패치 |
| 3 | FULL 모드인 경우 `docs/sdd/design/ui/` + `docs/sdd/design/api/` 존재 | **Phase 2로 롤백** — 누락분 복원 |
| 4 | FULL 모드인 경우 `context/{YYYY-MM-DD}-{feature}.md` 존재 | **Phase 2로 롤백** — context-manager 재디스패치 |
| 5 | Phase 2 최종 사용자 승인 기록 (design/arch + ui + api) | 사용자 승인 요청 |

### 프로세스

```
1. sdd-taskmaster 디스패치 (모드: tasks)
   - 입력: spec + design/arch + design/ui + design/api 문서 + worktree 경로
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

## 관련 문서 (spec, arch, ui, api 경로)
## 구현자 / 테스트 타입 (단위/통합/E2E)
## 완료 조건 (checkbox)
## 의존 태스크
## 예상 변경 파일 (모듈/경로 수준)
## Steps (checkbox)
## 검증 명령어
```
(테스트 시나리오는 test-automator가 task 완료 조건을 분석하여 직접 도출)

---

## Phase 4: Execute

**Phase 4는 sdd 리드가 직접 실행하지 않는다.** `sdd-orchestrator` 스킬이 전담한다.

### 진입 전 검증 (필수)

| # | 체크 | 실패 시 조치 |
|---|------|------|
| 1 | Phase 3 진입 전 검증 전부 통과 | **Phase 3 진입 전 검증으로 되돌아가기** |
| 2 | `docs/sdd/task/{feature}/` 아래 1개 이상의 task 문서 | **Phase 3으로 롤백** — taskmaster 재디스패치 |
| 3 | `ORCHESTRATOR_STATE.md` 존재 + 유효 스키마 | **Phase 3으로 롤백** — taskmaster dag 모드 재실행 |
| 4 | Phase 3 최종 사용자 승인 기록 (task + DAG/Wave) | 사용자 승인 요청 |

### 진입

Phase 2에서 이미 worktree가 생성되어 있다. 추가 생성 불필요.

1. worktree 경로에서 스냅샷 커밋 (`chore: Phase 4 실행 시작`)
   → PHASE4_WORKTREE_CREATED
2. ORCHESTRATOR_STATE.md의 **팀 배정 섹션** 확인:
   - **팀 배정 없음** (단일 체인) → `Skill(sdd-orchestrator)` 직접 호출 (기존 방식)
   - **팀 배정 있음** → Agent Team 생성:
     ```
     # 1. 팀 생성
     TeamCreate(team_name: "sdd-{feature}", description: "SDD Phase 4 실행")

     # 2. 각 팀에 대해
     Agent(
       team_name: "sdd-{feature}",
       name: "team-{N}",
       subagent_type: "sdd-team-leader",
       prompt: "Team {N} 담당. STATE.md 경로: {path}. 워크트리: {worktree_path}"
     )
     ```
3. Agent Team 모드에서 리더 역할:
   - 팀원 유휴 알림 수신 → STATE.md 전체 요약 업데이트
   - 모든 팀 COMPLETED → 통합 검증 단계 진행
   - 팀 실패(FAILED) → SendMessage로 해당 팀에 재지시 또는 사용자 에스컬레이션

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
| Phase 1 → 2 | spec + blocker-checker PASS + 사용자 승인 |
| Phase 2 모드 | SIMPLE/FULL 사용자 확인 |
| Phase 2 → 3 | design/arch + (FULL 시 design/ui, design/api, context) + 사용자 승인 |
| Phase 3 → 4 | task 문서 + ORCHESTRATOR_STATE + DAG/Wave + 사용자 승인 |
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

Phase 4 도중: 현재 태스크 완료 → spec v2 수정 → blocker-checker 재실행 → (FULL) design/arch/ui/api 영향 분석 → 해당 문서 수정 → 승인 → Phase 4 재개.

## 멀티 feature / 하위 호환성

- 각 feature는 독립 worktree + 독립 문서. 동시 진행 가능.
- SIMPLE 모드가 기본. context/design 없으면 호환 모드 폴백. 마이그레이션 불필요.
