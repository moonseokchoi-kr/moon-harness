---
name: sdd
description: "Use when a user mentions a feature idea, requirement, or spec document, or asks to implement something new — even if described informally or briefly"
---

# SDD (Spec-Driven Development)

기능 아이디어를 **Spec → Develop → Task** 3단계로 구조화하여 구현하는 워크플로우.

**핵심 원칙:** 문서가 곧 상태. 별도 상태 파일 없이 문서 존재 여부 + checkbox + 라벨로 Phase를 추적한다.

<HARD-GATE>
Phase 순서를 건너뛰지 않는다. Phase 1 없이 Phase 2로, Phase 2 없이 Phase 3으로 진입하지 않는다.
blocker-checker 통과 + 사용자 승인 없이 Phase 1에서 Phase 2로 진행하지 않는다.
develop 문서에 대한 사용자 명시적 승인 없이 Phase 3에 진입하지 않는다.
</HARD-GATE>

<HARD-GATE>
TDD Iron Law — TDD == FULL 태스크에서 다음을 위반하지 않는다:
1. RED 먼저: test-automator(tdd)가 실패하는 테스트를 작성하기 전에 구현 코드를 작성하지 않는다.
2. 테스트 보호: 구현자(implementer/engineer)는 테스트 파일(.test., .spec., _test.)을 수정하지 않는다.
3. GREEN 필수: 모든 TDD 테스트가 통과하지 않으면 태스크를 완료로 표기하지 않는다.
4. 리뷰 필수: reviewer 리뷰 없이 VERIFY 단계로 진행하지 않는다.
</HARD-GATE>

<HARD-GATE>
Phase 3 격리: 모든 Phase 3 구현은 worktree 안에서 수행한다. worktree 없이 main 브랜치에서 직접 코드를 수정하지 않는다.
</HARD-GATE>

<HARD-GATE>
Adversarial Escalation: 구현→리뷰 이터레이션 3회 소진 시 adversarial-review 스킬을 호출한다. adversarial review마저 BLOCKED이면 설계 결함으로 판정하고 worktree를 폐기한다.
</HARD-GATE>

<HARD-GATE>
의존 태스크 순서: 의존 태스크가 DONE 상태가 아니면 해당 태스크를 시작하지 않는다. 의존 관계를 무시하고 병렬 실행하지 않는다.
</HARD-GATE>

## Red Flags

| 합리화 | 현실 |
|--------|------|
| "스펙이 짧으니 검사 생략" | 짧은 스펙일수록 누락이 많다 |
| "develop 없이 바로 태스크" | 설계 없는 구현은 재작업을 낳는다 |
| "이슈 1개니 그냥 진행" | 이슈 1개도 반드시 사용자 확인 |
| "compliance check 이미 했으니 리뷰 생략" | 스펙 준수와 코드 품질은 별개 |
| "간단한 변경이라 worktree 불필요" | 모든 Phase 3 작업은 격리 필수 |
| "SIMPLE이면 충분하다" | 사용자가 FULL을 원하면 FULL로 전환 |
| "View라서 TDD 불필요" | View도 verify 모드 테스트는 필수 |
| "테스트가 간단하니 생략" | FULL TDD 태스크는 RED 단계 생략 불가 |
| "테스트를 살짝 수정하면 통과" | implementer는 테스트 코드 수정 금지 |

## 문서 구조

```
docs/sdd/
├── spec/{YYYY-MM-DD}-{feature}.md
├── design/                              # [FULL 모드 전용]
│   ├── ui/{YYYY-MM-DD}-{feature}.md     # UI/UX 명세
│   ├── api/{YYYY-MM-DD}-{feature}.md    # API 계약
│   └── review/{YYYY-MM-DD}-{feature}.md # 아키텍처 리뷰
├── context/{YYYY-MM-DD}-{feature}.md    # [FULL 모드] 공유 컨텍스트
├── develop/{YYYY-MM-DD}-{feature}.md
├── task/{feature}/{YYYY-MM-DD}-{task}.md
└── result/{YYYY-MM-DD}-{feature}.md
```

파일명: `{YYYY-MM-DD}-{feature-name}.md` (kebab-case, 영문). 동일 날짜+feature 조합이 존재하면 덮어쓰지 않고 사용자에게 알림.

## Phase 판정 규칙 (세션 재개 시)

세션 시작 시 `docs/sdd/` 디렉토리를 스캔하여 Phase를 자동 판정한다.

### 정밀 모드 (context 문서가 존재하는 경우)

context 문서의 `## 라벨 상태` 섹션에서 현재 라벨을 읽어 정확한 지점을 판정한다.

### 호환 모드 (context 문서가 없는 경우)

1. spec 문서 없음 → Phase 1 미시작
2. spec 문서 있음 + develop 문서 없음 → Phase 1 완료, Phase 2 미시작
3. develop 문서 있음 + task 문서 없음 → Phase 2 완료, Phase 3 미시작
4. task 문서 있음 + checkbox 미완료 항목 존재 → Phase 3 진행 중
5. 모든 task checkbox 완료 + result 문서 없음 → Phase 3 완료 대기
6. result 문서 있음 → 전체 완료

## 라벨 기반 상태 머신

context 문서의 `## 라벨 상태` 섹션에 현재 상태를 기록한다. **컨트롤러만 라벨을 변경**할 수 있다.

```
PHASE1_SPEC_DRAFT → PHASE1_BLOCKER_CHECK_PASS → PHASE1_USER_APPROVED
→ PHASE2_START → PHASE2_UI_DESIGN_COMPLETE → PHASE2_API_DESIGN_COMPLETE
→ PHASE2_ARCH_REVIEW_PASS → PHASE2_DEVELOP_INTEGRATED → PHASE2_USER_APPROVED
→ PHASE3_WORKTREE_CREATED
→ PHASE3_TASK_{N}_TEST_RED → PHASE3_TASK_{N}_IMPLEMENTING → PHASE3_TASK_{N}_REVIEWING
→ (이슈 시 IMPLEMENTING으로 복귀, 최대 3회) → PHASE3_TASK_{N}_GREEN
→ PHASE3_TASK_{N}_VERIFYING → (반려 시 IMPLEMENTING으로 복귀, 최대 3회) → PHASE3_TASK_{N}_VERIFIED
→ PHASE3_TASK_{N}_REFACTOR_TESTED → PHASE3_TASK_{N}_DONE
→ PHASE3_ALL_TASKS_DONE → PHASE3_INTEGRATION_TEST_PASS → PHASE3_RESULT_GENERATED → PHASE3_MERGED
```

라벨은 **전진만 가능**. 이전 상태로 되돌리는 것은 스펙 변경 정책에서만 허용.

## 에이전트 출력 표준

모든 SDD 에이전트는 다음 4개 상태 중 하나로 보고한다:

| 상태 | 의미 | 컨트롤러 행동 |
|------|------|--------------|
| `DONE` | 작업 완료 | 다음 단계로 진행 |
| `DONE_WITH_CONCERNS` | 완료했지만 우려사항 있음 | 우려사항 검토 후 진행 여부 결정 |
| `NEEDS_CONTEXT` | 정보 부족으로 진행 불가 | 누락 컨텍스트 제공 후 재파견 |
| `BLOCKED` | 근본적 문제로 진행 불가 | 원인 파악 → 에스컬레이션 |

재시도 한계: compliance-checker/reviewer **최대 3회**. 3회 초과 시 태스크 설계 재검토 → 사용자에게 에스컬레이션.

## 에이전트 목록 및 모델 배정

| 에이전트 | Phase | 모델 | 역할 |
|---------|-------|------|------|
| `sdd-blocker-checker` | 1 | haiku | spec 문서 블로커 탐지 |
| `sdd-context-manager` | 전체 | haiku | 공유 상태 관리 (라벨, API 계약, 파일 소유권) |
| `sdd-ui-designer` | 2 | opus | UI/UX 명세 작성 |
| `sdd-api-designer` | 2 | opus | API 계약 정의 |
| `sdd-architect-reviewer` | 2 | opus | 설계 정합성 검증 |
| `sdd-implementer` | 3 | sonnet | 범용 구현 (스택 전용 에이전트 없을 때) |
| `sdd-ts-engineer` | 3 | sonnet | TypeScript/Node.js 구현 |
| `sdd-rust-engineer` | 3 | sonnet | Rust 백엔드 구현 |
| `sdd-react-specialist` | 3 | sonnet | React 프론트엔드 구현 |
| `sdd-nextjs-engineer` | 3 | sonnet | Next.js 풀스택 구현 |
| `sdd-vue-engineer` | 3 | sonnet | Vue 3/Nuxt 3 구현 |
| `sdd-swift-engineer` | 3 | sonnet | Swift/iOS/macOS 구현 |
| `sdd-cpp-engineer` | 3 | sonnet | C++20/23 시스템 구현 |
| `sdd-flutter-engineer` | 3 | sonnet | Flutter/Dart 크로스플랫폼 구현 |
| `sdd-fastapi-engineer` | 3 | sonnet | FastAPI/Python API 구현 |
| `sdd-python-engineer` | 3 | sonnet | Python 일반 구현 |
| `sdd-sql-engineer` | 3 | sonnet | SQL/DB 스키마 구현 |
| `sdd-taskmaster` | 3 | sonnet | develop 태스크 테이블 → 상세 task 문서 생성 (sdd-taskrunner 스킬) |
| `sdd-compliance-checker` | 3 | sonnet | 스펙 준수 검증 |
| `sdd-reviewer` | 3 | sonnet | 코드 품질 리뷰 — P1(기능/아키텍처) 판정 (구현→리뷰 이터레이션) |
| `sdd-performance-engineer` | 3 | sonnet | 성능 검증 — P2(성능 안티패턴, 벤치마크) 판정 |
| `sdd-test-automator` | 3 | sonnet | TDD 테스트 작성(tdd) + 검증(verify) + 회귀 안전망(refactor) |
| `adversarial-reviewer` | 3 | opus | reviewer 3회 소진 후 투입 — 접근법 비판 + 방향 전환 (adversarial-review 스킬) |

---

## Phase 1: Spec

### 프로세스

1. 기존 spec 문서 확인 (`docs/sdd/spec/` 스캔)
2. 없으면 사용자와 대화로 초안 작성 (질문 하나씩)
3. spec 문서 저장: `docs/sdd/spec/{YYYY-MM-DD}-{feature}.md`
4. `sdd-blocker-checker` 에이전트 디스패치 (spec 전문을 prompt에 주입)
5. 블로커 발견 시: 수정 제안 → 사용자 승인 → 문서 수정 → 재검사
6. 블로커 없음: 사용자에게 "spec을 확인했습니다. Phase 2로 진행할까요?" 게이트

### spec 문서 템플릿

```markdown
# {Feature Name}

## 목표
무엇을 왜 만드는가.

## 범위
포함하는 것 / 포함하지 않는 것.

## 기능 요구사항
- [ ] 요구사항 1
- [ ] 요구사항 2

## 비기능 요구사항
성능, 보안, 접근성 등.

## 제약조건
기술 스택 제한, 호환성 요구 등.

## 용어 정의
도메인 용어 설명 (필요 시).
```

---

## Phase 2: Develop

### 설계 모드 판정

Phase 2 진입 시 다음 기준으로 **SIMPLE/FULL** 모드를 판정한다:

| 조건 | 모드 |
|------|------|
| spec의 기능 요구사항이 3개 이하 + API/UI 미언급 | SIMPLE |
| spec에 "API", "엔드포인트", "화면", "컴포넌트" 등 키워드 존재 | FULL |
| spec의 제약조건에 프론트엔드+백엔드 기술 스택이 모두 존재 | FULL |
| 사용자가 명시적으로 "간단하게" 요청 | SIMPLE |
| 사용자가 명시적으로 "설계부터" 요청 | FULL |

판정 결과를 사용자에게 제시: "이 프로젝트는 [SIMPLE/FULL] 설계 모드로 진행합니다. 변경하시겠습니까?"

### SIMPLE 모드 (기존 방식)

1. **프로젝트 컨텍스트 탐색** — 관련 코드, 문서, 최근 커밋 확인
2. **기술 질문 (하나씩)** — 사용자와 대화하며 설계 결정
3. **접근법 2-3개 제안** — 트레이드오프와 권장안 포함
4. **태스크 분해** — 각 태스크는 독립 커밋 가능한 단위
5. **develop 문서 저장**: `docs/sdd/develop/{YYYY-MM-DD}-{feature}.md`
6. **사용자 승인 게이트** — 명시적 승인 전까지 Phase 3 진입 불가

### FULL 모드 (에이전트 파이프라인)

```
Step 1: context-manager INIT 디스패치
        → context 문서 생성, 라벨: PHASE2_START

Step 2: sdd-ui-designer 디스패치
        - 입력: spec 전문 + 프로젝트 기술 스택
        - 출력: design/ui/ 문서
        → 라벨: PHASE2_UI_DESIGN_COMPLETE
        (백엔드 전용 프로젝트이면 이 단계 생략)

Step 3: sdd-api-designer 디스패치
        - 입력: spec 전문 + UI 명세 (있는 경우) + 기존 API 구조
        - 출력: design/api/ 문서
        → 라벨: PHASE2_API_DESIGN_COMPLETE

Step 4: [사용자 중간 확인 게이트]
        UI + API 설계를 사용자에게 제시하여 피드백 수집.
        수정이 필요하면 해당 에이전트 재디스패치.

Step 5: sdd-architect-reviewer 디스패치
        - 입력: spec + UI 명세 + API 계약 + 프로젝트 구조
        - 출력: design/review/ 문서
        - BLOCKED이면: 이슈 수정 후 재리뷰
        → 라벨: PHASE2_ARCH_REVIEW_PASS

Step 6: 컨트롤러가 develop 문서 통합 생성
        - design/ui/, design/api/, design/review/ 산출물을 통합
        - 구현자 배정 (rust-engineer / react-specialist / implementer) 포함
        → 라벨: PHASE2_DEVELOP_INTEGRATED

Step 7: [사용자 최종 승인 게이트]
        develop 문서 제시 + 사용자 명시적 승인
        → 라벨: PHASE2_USER_APPROVED
```

**순서 근거**: UI → API → Review. 화면이 데이터 요구를 결정 → API가 인터페이스를 확정 → 리뷰가 정합성을 검증.

### 태스크 분해 기준

- 각 태스크는 **독립 커밋 가능한 단위**
- 각 스텝은 **2-5분 내 완료 가능**
- 의존성이 있으면 **순서 번호로 명시**
- 병렬 실행 가능 여부 표기
- (FULL 모드) **구현자 유형 명시**: 구현자 선택 로직에 따라 배정
- **TDD 수준 표기**: 각 태스크에 FULL 또는 SKIP을 명시

### TDD 적용 판정

태스크별로 TDD 수준을 판정한다. 별도 테스트 태스크(T-N-test)를 만들지 않고, 태스크 내 서브스텝으로 처리한다.

| 레이어 | TDD 수준 | 근거 |
|--------|----------|------|
| Model/Service (비즈니스 로직, 유틸리티) | FULL | 순수 로직, 단위 테스트 용이 |
| ViewModel/Controller (상태 관리) | FULL | 상태 전이 로직, mock으로 의존성 격리 가능 |
| View/UI (DOM 조작, 렌더링) | SKIP | 통합 테스트로 대체 (test-automator verify 모드) |
| 설정/스캐폴딩 (config, manifest) | SKIP | 테스트 불필요 |
| DB 스키마/마이그레이션 | FULL | 데이터 무결성 검증 필수 |

- **FULL TDD**: test-automator(tdd) → RED 확인 → 구현자 GREEN → reviewer 이터레이션 → verify → refactor 테스트
- **SKIP TDD**: 구현자 → reviewer 이터레이션 → compliance → test-automator(verify)

### develop 문서 템플릿

```markdown
# {Feature Name} — 기술 설계

## 관련 spec
`docs/sdd/spec/{YYYY-MM-DD}-{feature}.md`

## 설계 산출물 참조 (FULL 모드)
- UI 명세: `docs/sdd/design/ui/{YYYY-MM-DD}-{feature}.md`
- API 계약: `docs/sdd/design/api/{YYYY-MM-DD}-{feature}.md`
- 아키텍처 리뷰: `docs/sdd/design/review/{YYYY-MM-DD}-{feature}.md`

## 아키텍처 결정
주요 설계 결정과 근거.

## API 설계
인터페이스, 커맨드, 데이터 흐름.

## 데이터 모델
스키마, 타입, 구조체.

## 테스트 전략

### 테스트 프레임워크
프로젝트에서 사용하는 테스트 프레임워크와 설정.
(예: vitest, jest, cargo test, pytest 등 — 기존 프레임워크가 없으면 제안)

### 코드 커버리지 전략

| 대상 | 목표 | 근거 |
|------|------|------|
| (예시) Model/Service 레이어 | 80%+ | 비즈니스 로직 핵심 |
| (예시) ViewModel/Controller | 70%+ | 상태 전이 로직 |
| (예시) View/UI | 측정 제외 | 프레임워크 의존, 통합 테스트로 대체 |
| (예시) 전체 (제외 대상 빼고) | 75%+ | MVP 기준선 |

커버리지 실행 명령어와 설정 파일에서의 측정 범위(include/exclude) 명시.

### 단위 테스트 대상 (TDD FULL)
| 모듈 | 테스트 대상 | 핵심 시나리오 |
|------|------------|-------------|
| (예시) TokenEstimator | estimate(), getModelLimit() | 한국어/영문 혼합, 빈 문자열, 모델별 한도 |

### 통합 테스트 대상 (verify 모드)
| 흐름 | 검증 내용 |
|------|----------|
| (예시) 메시지 전송 | ViewModel → PromptBuilder → Provider 파이프라인 |

### 성능 테스트 전략 (performance-engineer)
| 대상 | 측정 항목 | 기준선 | 도구 |
|------|----------|--------|------|
| (예시) API 응답 | p95 latency | < 200ms | k6, wrk |
| (예시) DB 쿼리 | 실행 시간 | < 50ms | EXPLAIN ANALYZE |

### 성능 안티패턴 감시
- [ ] N+1 쿼리
- [ ] O(n²) 이상 알고리즘
- [ ] 동기 블로킹 I/O
- [ ] 메모리 누수 (이벤트 리스너 미해제 등)

### View/UI 검증 방침
UI 컴포넌트는 TDD 대신 다음으로 검증:
- compliance-checker: UI 명세 준수 확인
- reviewer: 코드 품질 확인
- test-automator verify 모드: 통합 테스트

## 태스크 목록

| # | 태스크 | 구현자 | TDD | 의존 | 병렬 가능 |
|---|--------|--------|-----|------|----------|
| 1 | API 엔드포인트 구현 | rust-engineer | FULL | 없음 | - |
| 2 | DB 스키마 생성 | sql-engineer | FULL | T-1 | - |
| 3 | 로그인 화면 구현 | react-specialist | SKIP | T-1 | T-2와 병렬 |

## 변경 예상 파일
- `path/to/file.rs` — 역할
```

---

## Phase 3: Task

### 진입

1. spec의 feature name에서 브랜치명 도출: `feat/{feature-name}` (kebab-case)
2. `EnterWorktree` 도구 호출 (name: `{feature-name}`)
3. worktree 내에서 브랜치 이름 변경:
   ```bash
   git branch -m feat/{feature-name}
   ```
4. 스냅샷 커밋
5. (FULL 모드) context-manager에 태스크별 파일 소유권 초기 등록

### 구현자 선택 로직

develop 문서에 구현자가 명시되어 있으면 그것을 따른다. 없으면 프로젝트 스택과 변경 파일로 자동 선택:

| 스택 감지 | 구현자 |
|-----------|--------|
| `Cargo.toml` / `.rs` 파일 | `sdd-rust-engineer` |
| `package.json` + React (`react` 의존성) | `sdd-react-specialist` |
| `package.json` + Next.js (`next` 의존성) | `sdd-nextjs-engineer` |
| `package.json` + Vue/Nuxt (`vue`/`nuxt` 의존성) | `sdd-vue-engineer` |
| `package.json` + TypeScript (프레임워크 미특정) | `sdd-ts-engineer` |
| `pubspec.yaml` / `.dart` 파일 | `sdd-flutter-engineer` |
| `Package.swift` / `.swift` 파일 / Xcode | `sdd-swift-engineer` |
| `CMakeLists.txt` / `.cpp`/`.h` 파일 | `sdd-cpp-engineer` |
| `pyproject.toml` + FastAPI (`fastapi` 의존성) | `sdd-fastapi-engineer` |
| `pyproject.toml` / `requirements.txt` (일반 Python) | `sdd-python-engineer` |
| SQL 마이그레이션 / DB 스키마 태스크 | `sdd-sql-engineer` |
| 혼합 스택 (예: .rs + .tsx) | 백엔드 먼저 → context 갱신 → 프론트엔드 |
| 기타 | `sdd-implementer` (범용) |

### 심각도 체계

| 심각도 | 범위 | 판정 주체 | implementer 대응 |
|--------|------|----------|-----------------|
| `[P1]` | 기능 오류, 아키텍처 위반, 명백한 성능 안티패턴 | **reviewer** (정적 코드 리뷰) | **반드시 수정** — 미수정 시 BLOCKED |
| `[P2]` | 실측 성능 문제 (벤치마크/프로파일링 기반) | **performance-engineer** (동적 실행) | **반드시 수정** — 기준선 미달 시 BLOCKED |
| `[P3]` | 스타일, 네이밍, 포맷 | **린터/포매터** (도구 위임) | reviewer가 보고하지 않음 |

### 태스크마다 반복

```
1. (FULL 모드) context-manager TASK_START 디스패치
   - 파일 소유권 등록 + 충돌 검사
   - 충돌 시 BLOCKED → 의존 태스크 완료 대기

2. sdd-taskmaster 에이전트 병렬 디스패치
   - develop 태스크 테이블에서 전체 태스크 번호를 파악
   - 각 태스크마다 Agent(subagent_type="sdd-taskmaster")를 병렬 디스패치
   - prompt: develop 경로 + spec 경로 + 태스크 번호 + worktree 경로 + feature 이름 (최소 정보만)
   - 각 에이전트 내부에서: Skill(sdd-taskrunner) 호출 → Read → 복잡도 분석 → task 문서 작성
   - 메인 컨텍스트에는 완료 보고만 수신
   - 출력: docs/sdd/task/{feature}/{YYYY-MM-DD}-{task}.md

3. [TDD == FULL] RED 단계: sdd-test-automator 디스패치 (tdd 모드)
   - 입력: task 문서 전문 + develop 테스트 전략 섹션 + spec 관련 요구사항
   - (FULL 모드 추가) API 계약 + context 문서 주입
   - 행동: 실패하는 단위 테스트 작성 → 테스트 실행 → 전체 RED 확인
   - 출력: 테스트 파일 경로 + RED 상태 확인 보고
   → 라벨: PHASE3_TASK_{N}_TEST_RED

4. GREEN 이터레이션 루프 (최대 3회):
   ** 컨트롤러는 iteration: {현재}/{최대} 를 모든 에이전트 입력에 주입한다 **

   a. 구현자 디스패치 (선택 로직에 따라)
      - 입력: task 문서 전문 + develop 관련 섹션 + iteration: N/3
      - [TDD == FULL 추가] 테스트 파일 경로 + 실행 명령어 + "테스트 지속 실행" 지시
      - [2회차 이상] reviewer [P1] 피드백을 입력에 주입 → 해당 이슈만 수정
      - (FULL 모드 추가) API 계약 + UI 명세 + context 문서 주입
      - 완료 조건: 빌드 성공 + [TDD] 모든 테스트 통과 + 커밋
      → 라벨: PHASE3_TASK_{N}_IMPLEMENTING

   b. sdd-reviewer 디스패치
      - 입력: 변경 파일 경로 목록 + diff + [TDD] 테스트 파일 경로 + iteration: N/3
      - 검증: [P1] 기능 오류, 아키텍처 위반, [TDD] 테스트 코드 미수정 여부
      - [P1] 이슈 있음 → 피드백을 구현자 입력에 주입 → 4a로
      - [P1] 없음 → DONE으로 루프 탈출
      → 라벨: PHASE3_TASK_{N}_REVIEWING

   * 3회 후에도 [P1] 미해결 → adversarial-review 스킬 호출:
     - 입력: 변경 파일 + diff + reviewer 3회분 피드백 전체 + task 문서
     - adversarial-reviewer(opus)가 접근법 자체를 비판 → 구현자에게 대안 주입 → 재비판
     - PASS (니트픽 수준) → 루프 탈출
     - BLOCKED (대안 제시 불가) → 설계 결함 → worktree 폐기 + 사용자에게 보고
   → 루프 탈출 시 라벨: PHASE3_TASK_{N}_GREEN

5. VERIFY 단계 (최대 3회):
   a. sdd-compliance-checker 디스패치
      - 입력: spec 전문 + develop 전문 + 변경 파일 경로 목록
      - (FULL 모드 추가) design/api/ + design/ui/ 주입
      - 반려 → compliance 피드백을 주입하여 4번 GREEN 이터레이션 재진입

   b. sdd-test-automator 디스패치 (verify 모드)
      - 입력: task 문서 + 변경 파일 + [TDD] 기존 테스트 파일
      - 행동: 기존 TDD 테스트 재실행 + 추가 통합 테스트 작성/실행
      - 실패 → 실패 원인을 주입하여 4번 GREEN 이터레이션 재진입

   c. sdd-performance-engineer 디스패치
      - 입력: 변경 파일 + develop 성능 테스트 전략 섹션
      - 행동: 벤치마크 실행, 프로파일링, 성능 안티패턴 감지
      - [P2] 이슈 발견 → 피드백을 주입하여 4번 GREEN 이터레이션 재진입
      - 성능 기준선 충족 → DONE

   * 3회 후 미통과 → adversarial-review 스킬 호출 (VERIFY 실패 원인 + 피드백 주입)
     - BLOCKED → 설계 결함 → worktree 폐기 + 사용자에게 보고
   → 라벨: PHASE3_TASK_{N}_VERIFIED

6. [TDD == FULL] REFACTOR 테스트 단계: sdd-test-automator 디스패치 (refactor 모드)
   - 입력: task 문서 + 변경 파일 + 기존 테스트 파일
   - 행동: 엣지 케이스 보강 + 모듈 간 계약 테스트 + 성능 회귀 테스트 작성
   - 출력: 추가 테스트 파일 + 실행 결과
   → 라벨: PHASE3_TASK_{N}_REFACTOR_TESTED

7. (FULL 모드) context-manager TASK_COMPLETE 디스패치
   - 소유권 해제 + 공유 타입 갱신 + 라벨 갱신

8. task checkbox 완료 표기
   → 라벨: PHASE3_TASK_{N}_DONE
```

### SKIP TDD 분기

TDD == SKIP인 태스크는 3번(RED)과 6번(REFACTOR)을 건너뛴다:

```
2. sdd-taskmaster 병렬 디스패치 → task 문서 생성
4. GREEN 이터레이션: 구현자 → reviewer [P1] → (이터레이션)
5. VERIFY: compliance → test-automator(verify) → performance-engineer [P2]
→ TASK DONE
```

### TDD 실패 복구 흐름도

```
taskmaster N개 병렬 디스패치 → task 문서 일괄 생성
  ↓
[태스크별 반복 시작]
[TDD FULL] RED (test-automator tdd)
  ├─ DONE → GREEN 이터레이션 진입
  ├─ NEEDS_CONTEXT → 컨텍스트 보충 → RED 재시도
  └─ BLOCKED → 사용자 에스컬레이션

GREEN 이터레이션 (최대 3회, iteration: N/3 추적):
  구현자 → reviewer [P1] → P1 있음? → 피드백 주입 → 구현자 → ...
  ├─ P1 없음 → VERIFY 진입
  └─ 3회 소진 + P1 잔존 → adversarial-review 호출
     ├─ PASS (니트픽) → VERIFY 진입
     └─ BLOCKED → 설계 결함 → worktree 폐기

VERIFY (최대 3회):
  compliance → 반려? → GREEN 재진입
  test-automator verify → 실패? → GREEN 재진입
  performance-engineer → [P2] 발견? → GREEN 재진입
  ├─ 전체 통과 → [TDD FULL] REFACTOR 테스트 → DONE
  └─ 3회 소진 → adversarial-review 호출 → BLOCKED → worktree 폐기
```

### 병렬 실행 규칙

- 허용: rust-engineer ∥ react-specialist (파일 영역이 다른 경우)
- 금지: 같은 유형 에이전트 병렬 실행 (워크트리 내 충돌 위험)
- (FULL 모드) context-manager CONFLICT_CHECK로 사전 검증
- 의존 태스크가 `DONE`이 아니면 시작 불가

### 혼합 태스크 처리 (Rust + React)

하나의 태스크가 Rust + React 파일을 모두 변경해야 하는 경우:
1. rust-engineer를 먼저 디스패치 (API 구현이 먼저)
2. 완료 후 context-manager TASK_COMPLETE (실제 API 타입 기록)
3. react-specialist를 디스패치 (context 문서의 실제 타입 참조)

### BLOCKED 처리

1. 컨텍스트 부족 → 추가 컨텍스트 제공 후 재파견
2. 태스크 과대 → 분할
3. 설계 결함 (adversarial review BLOCKED) → worktree 폐기 (`ExitWorktree` action: `"discard"`) + 사용자에게 보고
4. (FULL 모드) 파일 소유권 충돌 → 의존 태스크 완료 대기

### 모든 태스크 완료 후: 최종 통합 검증

각 태스크별 verify가 이미 통과했으므로, 여기서는 **태스크 간 통합**만 검증한다.

```
1. sdd-test-automator 디스패치 (verify 모드 - 통합)
   - 입력: spec + develop + API 계약 + 변경 파일 전체 + context + 각 태스크 테스트 파일
   - 행동: 기존 단위 테스트 전체 실행 + 크로스 태스크 통합 테스트 작성/실행
   - 출력: 테스트 결과 + 실패 원인 분석

2. 실패 시:
   a. test-automator가 원인 에이전트를 특정
   b. 해당 에이전트 재디스패치 (실패 테스트 정보 + 수정 지시 주입)
   c. 수정 후 test-automator 재실행 (최대 2회)
   d. 2회 후에도 실패 시 사용자 에스컬레이션

3. 전체 통과 시: Phase 3 완료 단계로 진행
```

### task 문서 템플릿

```markdown
# T-{N}: {Task Name}

## 관련 문서
- spec: `docs/sdd/spec/{YYYY-MM-DD}-{feature}.md`
- develop: `docs/sdd/develop/{YYYY-MM-DD}-{feature}.md`

## 구현자
{구현자 선택 로직에 따라 배정}

## TDD 수준
{FULL | SKIP}
사유: {SKIP이면 사유 기술 (예: "View 레이어 — 통합 테스트로 대체")}

## 완료 조건
- [ ] 조건 1
- [ ] 조건 2
- [ ] [TDD == FULL] 모든 단위 테스트 통과

## 테스트 시나리오 (TDD == FULL)
test-automator(tdd 모드)가 이 시나리오를 기반으로 테스트를 작성한다.

| # | 시나리오 | 입력 | 기대 결과 | 유형 |
|---|----------|------|----------|------|
| 1 | 정상 동작 | 유효한 입력 | 기대 출력 | unit |
| 2 | 빈 입력 처리 | 빈 문자열 | 기본값 반환 | unit |
| 3 | 에러 케이스 | 잘못된 형식 | 에러 반환 | unit |

## 의존 태스크
없음 / T-{M}

## 예상 변경 파일
- `path/to/file` — 변경 내용

## Steps
- [ ] Step 1: ...
- [ ] Step 2: ...

## 검증 명령어
```bash
npm test -- --run
```
```

---

## Phase 3 완료

1. **컨트롤러가 result 문서 생성 + 커밋**: `docs/sdd/result/{YYYY-MM-DD}-{feature}.md`
2. **worktree 종료**: `ExitWorktree` (action: `"keep"`) — 원본 repo로 복귀
3. **main에 머지**:
   ```bash
   git merge feat/{feature-name} --no-ff -m "feat: {Feature Name} 구현"
   ```
4. **정리**:
   ```bash
   git worktree remove worktrees/{feature-name}
   git branch -d feat/{feature-name}
   ```
5. 사용자에게 결과 보고 (result 문서 내용 요약)

> 머지 충돌 발생 시: 충돌 내용을 사용자에게 보고하고 해결 요청. 해결 후 머지 재시도.

### result 문서 템플릿

```markdown
# {Feature Name} — 결과

## 설계 모드
{SIMPLE | FULL}

## 머지
main에 머지 완료 (원본 브랜치: `feat/{feature-name}`)

## 구현 태스크
- [x] T-1: ... (rust-engineer)
- [x] T-2: ... (react-specialist)

## 변경 파일
- `path/to/file.rs`
- `path/to/file.tsx`

## 리뷰 요약
- Critical 이슈: 0건
- Important 이슈: N건 (모두 해결됨)
- Minor 이슈: N건 (참고)

## 테스트 요약 (FULL 모드)
- 통합 테스트: N개 통과
- E2E 테스트: N개 통과
```

---

## 게이트 정책

| 전환 | 게이트 |
|------|--------|
| Phase 1 → 2 | blocker-checker 결과 + "spec을 확인했습니다. Phase 2로 진행할까요?" |
| Phase 2 모드 판정 | SIMPLE/FULL 판정 결과 사용자 확인 |
| Phase 2 중간 확인 (FULL) | UI + API 설계 완료 후, architect-reviewer 전 |
| Phase 2 → 3 | develop 문서 제시 + 사용자 명시적 승인 |
| Phase 3 RED → GREEN | [TDD FULL] test-automator(tdd) DONE → 구현자 디스패치 허용 |
| Phase 3 GREEN → VERIFY | [TDD FULL] 모든 테스트 통과 + reviewer 통과 → compliance/verify 진행 |
| Phase 3 → 최종 통합 | 모든 태스크 DONE → 크로스 태스크 통합 검증 |
| Phase 3 완료 | 통합 테스트 통과 → result 문서 생성 → 자동 머지 + worktree 정리 |
| Phase 3 중단 | 사용자가 "중단"하면 현재 태스크 완료 후 result 문서 생성 → 머지/정리 진행 |
| 태스크 스킵 | 사용자가 "T-N 스킵"하면 develop 문서에 스킵 사유 기록 후 다음 태스크 |
| Phase 3 → 4 | 사용자 명시적 요청 ("배포해줘", "ship", "리뷰해줘") |
| Phase 4-1 → 4-2 | 리뷰 Critical 항목 전부 PASS |
| Phase 4-2 → 4-3 | 머지 + CI 통과 |
| Phase 4-3 → 완료 | Verify 체크리스트 통과 |

## CLAUDE.md 규칙 매핑

| CLAUDE.md 규칙 | SDD 적용 시점 |
|---------------|--------------|
| 작업 전 스냅샷 커밋 | Phase 3 진입 시 worktree 생성 직후 1회 |
| 서브태스크별 커밋 (`feat: T-XX-N`) | 구현자 에이전트가 각 스텝 완료 시 |
| 브랜치 작업 원칙 (`feat/{feature-name}`) | Phase 3 진입 시 EnterWorktree + branch rename |

## 스펙 변경 정책

Phase 3 도중 스펙 변경이 필요한 경우:
1. 현재 태스크 완료 후 중단
2. spec 문서 수정 (버전 표기: v2)
3. blocker-checker 재실행
4. (FULL 모드) design/ 문서 영향 분석 → 필요시 해당 에이전트 재디스패치
5. develop 문서 영향 분석 → 필요시 수정
6. 사용자 승인 후 Phase 3 재개

## 멀티 feature 정책

- 각 feature는 독립 worktree + 독립 문서 세트
- 동시 진행 가능 (문서 경로에 feature명 포함되어 충돌 없음)

## 하위 호환성

- **SIMPLE 모드가 기본**: 명시적 조건 충족 없이는 기존 방식 유지
- **sdd-implementer 유지**: Rust/React 외 프로젝트에서 범용 구현자로 사용
- **context 문서 없이도 동작**: context 문서가 없으면 호환 모드(기존 문서 존재 규칙)로 폴백
- **design/ 없이도 동작**: SIMPLE 모드에서는 design/ 디렉토리 불필요
- **마이그레이션 불필요**: 기존 프로젝트는 자동으로 호환 모드

---

## Phase 4: Review → Ship → Verify (선택적)

Phase 3 완료 후, 사용자가 원하면 배포 파이프라인으로 진행한다.
**Phase 4는 자동으로 시작되지 않는다.** 사용자가 "배포해줘", "ship", "리뷰해줘" 등을 명시적으로 요청할 때 진행.

### Phase 4-1: Review (코드 리뷰)

Phase 3에서 만든 코드를 **구현과 다른 관점**에서 검증한다.

#### 리뷰 체크리스트

```markdown
## 보안
- [ ] 외부 입력 검증 (SQL 인젝션, XSS)
- [ ] 인증/인가 체크
- [ ] 시크릿 하드코딩 없음

## 품질
- [ ] 에러 핸들링 (catch에서 무시하지 않음)
- [ ] 타입 안전성 (any 남용 없음)
- [ ] 테스트 커버리지 (핵심 로직)

## 아키텍처
- [ ] 레이어 의존성 방향 준수
- [ ] 불필요한 의존성 추가 없음
- [ ] 기존 패턴과 일관성

## 스펙 준수
- [ ] spec 문서의 모든 요구사항 구현됨
- [ ] MVP 범위를 벗어난 기능 없음
```

#### 리뷰 프로세스

1. Phase 3의 diff를 전체 검토
2. 체크리스트 항목별 PASS/FAIL 판정
3. FAIL 항목이 있으면:
   - Critical: 즉시 수정 (Phase 3 에이전트 재디스패치)
   - Non-critical: docs/pitfalls.md에 기록 후 진행 가능
4. 3회 리뷰 실패 → adversarial-review 에스컬레이션 (기존 메커니즘 활용)
5. 리뷰 통과 → Phase 4-2로

### Phase 4-2: Ship (배포 준비)

코드를 머지하고 배포할 준비를 한다.

#### Ship 체크리스트

```markdown
## 머지 전
- [ ] 모든 테스트 통과 (로컬)
- [ ] 리뷰 통과
- [ ] 커밋 메시지 정리 (squash 또는 정리)
- [ ] CHANGELOG 업데이트 (있는 경우)
- [ ] docs/ 문서 갱신 확인

## 머지
- [ ] PR 생성 (또는 직접 머지)
- [ ] CI 통과 확인 (CI가 있는 경우)
```

#### Ship 프로세스

1. 커밋 정리 (필요시 squash)
2. PR 생성 또는 머지 수행
3. CI 결과 대기 (CI가 있는 경우)
4. 머지 완료 → Phase 4-3으로

### Phase 4-3: Verify (배포 후 검증)

배포 후 실제로 동작하는지 확인한다.

#### Verify 체크리스트

프로젝트 유형에 따라 적절한 검증 수행:

```markdown
## 웹 서비스
- [ ] 헬스 체크 엔드포인트 응답 확인
- [ ] 핵심 API 엔드포인트 스모크 테스트
- [ ] 콘솔 에러 없음

## 라이브러리
- [ ] 패키지 빌드 성공
- [ ] 예제 코드 실행 확인

## CLI 도구
- [ ] 설치 후 기본 명령어 동작 확인
- [ ] --help 출력 확인
```

#### Verify 프로세스

1. 배포 대상에 맞는 검증 실행
2. 문제 발견 시:
   - 즉시 수정 가능 → 핫픽스 + 재배포
   - 롤백 필요 → 사용자에게 알리고 판단 위임
3. 검증 통과 → result 문서에 배포 결과 추가

### Phase 4 게이트

| 전환 | 게이트 |
|------|--------|
| Phase 3 → 4-1 | 사용자 명시적 요청 (자동 진입 아님) |
| 4-1 → 4-2 | 리뷰 체크리스트 모든 Critical 항목 PASS |
| 4-2 → 4-3 | 머지/CI 통과 |
| 4-3 → 완료 | Verify 체크리스트 통과 |

### Phase 4 Result 문서 추가

Phase 4 완료 시 기존 result 문서에 추가:

```markdown
## 배포 결과
- 리뷰: {통과/N회 수정 후 통과}
- 머지: {PR #N / 직접 머지}
- CI: {통과/해당 없음}
- 배포 검증: {통과/이슈 N건 핫픽스}
- 배포일: {YYYY-MM-DD}
```
