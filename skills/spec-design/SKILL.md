---
name: spec-design
description: "Use when a user mentions a feature idea, requirement, or spec document, or asks to create requirement specifications and design artifacts (architecture, IA, UI, API contracts) — the structured design workflow that runs up to (but not including) implementation"
---

# Spec-Design (요구 명세 + 설계)

기능 아이디어를 **Phase 1 (Spec) → Phase 2 (Design: arch/ui/api)** 2단계로 구조화하여 구현 직전까지의 설계 산출물을 생산하는 워크플로우.
spec-design 리드는 **순수 팀장**이다. 직접 문서를 작성하지 않고, 관리/보고/승인/에스컬레이션만 담당한다.

**핵심 원칙:** 문서가 곧 상태. 문서 존재 여부 + checkbox + 라벨로 Phase를 추적한다.

> **주의:** 이 스킬은 **구현(코드 작성)을 포함하지 않는다**. Phase 2 최종 승인 이후 구현은 사용자가 별도 도구/워크플로우로 진행한다.

---

## 자동 파이프라인 모드 (기본)

spec-design은 **Stop 훅 파이프라인 컨트롤러**로 자동 진행된다. 사용자가 `/spec-design start` 한 번만 실행하면 Phase 2 최종 승인까지 자동. 각 Phase 사이의 사용자 승인 게이트에서만 멈춤.

### 시작

```bash
# 사용자 요청 감지 시
source "$HARNESS_HOOKS/enforcement/lib/pipeline-utils.sh"
init_pipeline "<feature-name>" "<WITH_UI|WITHOUT_UI>"
```

- `WITH_UI`: UI가 있는 기능 (프론트엔드 포함). IA/UI/API 전부 필요
- `WITHOUT_UI`: 순수 백엔드/라이브러리 기능. arch + API만

### 흐름

```
init_pipeline → Claude가 작업 → Stop 훅 → directive 주입 → 다음 작업
                                    ↓
                        (반복, 라벨 따라 자동 전진)
                                    ↓
            사용자 게이트 도달 → waiting_for_user=true → Claude 멈춤
                                    ↓
            사용자 응답 → pipeline.json 갱신 → 재개
                                    ↓
            PHASE2_FINAL_APPROVED → 파이프라인 종료
```

### 사용자 승인 감지 (자연어)

`waiting_for_user=true` 상태에서 사용자 응답 받으면:

| 응답 | 처리 |
|------|------|
| "승인", "좋아", "진행", "ok", "go" | `advance_label <next>` + `set_waiting_for_user false null` |
| "X를 수정해줘", "Y 바꿔줘" | 해당 phase로 롤백 + 수정 요청을 담당 agent에게 전달 |
| "취소", "중단" | `cancel_pipeline` |

### 핵심 헬퍼 함수 (`pipeline-utils.sh`)

```bash
init_pipeline <feature> <mode>      # 파이프라인 시작 (mode: WITH_UI|WITHOUT_UI)
advance_label <new_label>           # 다음 라벨로 전이
set_waiting_for_user <bool> <type>  # 사용자 게이트 설정/해제
set_worktree_path <path>            # worktree 경로 기록
cancel_pipeline                     # 파이프라인 종료
show_pipeline                       # 현재 상태 조회
```

### Stop 훅 Directive 우선

**Stop 훅이 block + directive를 반환하면 directive를 최우선으로 따른다.**

directive는 라벨별로 "지금 무엇을 할지"를 구체적으로 지시한다. Phase 판정, 에이전트 선택, 파일 경로가 모두 포함된다. 혼동이 생기면 아래 "참조 절차" 섹션을 보되 directive와 충돌하면 directive 우선.

### 파이프라인 재개 / 취소

- 재개: 같은 프로젝트의 다음 세션에서 자동 재개 (pipeline.json + session_id 매칭)
- 취소: `cancel_pipeline` 또는 `.claude/state/pipeline.json` 삭제

---

## 참조 절차 (directive 상세 해설)

아래 내용은 파이프라인 directive가 지시하는 각 단계의 상세 절차다.
일반적으로 directive만 따르면 되지만, 특수 상황(복수 기능, 복잡한 의존성)에서는 이 절차를 참조한다.

<HARD-GATE>
1. Phase 순서를 건너뛰지 않는다. 직전 Phase 산출물이 불완전하면 해당 Phase로 롤백해서 복원 후 재진입.
   blocker-checker 통과 + 사용자 승인 없이 Phase 2 진입 불가.
   → 선행조건 미충족 시 phase-gate.sh가 세션 시작 시 자동 경고한다.
2. Phase 2 격리: 모든 설계 산출물은 worktree 안에서 수행.
3. Phase 2 모드 준수: WITH_UI 모드는 ui 명세 없이 api 진입 불가. WITHOUT_UI는 ui 단계 자체를 skip.
</HARD-GATE>

## Anti-Patterns (HARD-GATE 위반 트리거)

아래 합리화가 감지되면 즉시 중단하고 올바른 절차로 돌아간다.

| 합리화 | 실제 결과 | 올바른 행동 |
|--------|----------|------------|
| "스펙이 짧으니 검사 생략" | 짧은 스펙일수록 누락이 많다 | blocker-checker 실행 |
| "설계 없이 바로 구현" | 설계 없는 구현은 재작업을 낳는다 | Phase 2 설계 먼저, 구현은 별도 워크플로우 |
| "이슈 1개니 그냥 진행" | 이슈 1개도 쌓이면 P1 | 사용자 확인 후 진행 |
| "UI 없어도 arch만 해도 됨" | WITH_UI 모드면 UI·API 모두 필수 | 모드를 WITHOUT_UI로 재선택하거나 UI 진행 |

## 문서 구조

```
docs/spec-design/
├── spec/{YYYY-MM-DD}-{feature}.md       # Phase 1 요구 명세
└── design/                              # Phase 2 설계
    ├── arch/{YYYY-MM-DD}-{feature}.md   # 아키텍처 (모든 모드)
    ├── ui/{YYYY-MM-DD}-{feature}.md     # UI/UX 명세 (WITH_UI 모드)
    └── api/{YYYY-MM-DD}-{feature}.md    # API 계약

.claude/state/
└── pipeline.json                        # 파이프라인 상태 (current_label, waiting_for_user 등)
                                         # init_pipeline 시 생성, cancel_pipeline 시 삭제
```

파일명: `{YYYY-MM-DD}-{feature-name}.md` (kebab-case, 영문).

## Phase 판정 규칙 (세션 재개 시)

**호환 모드** (context 없음) — 직전 Phase 산출물이 **완전할 때만** 다음 Phase로 진입 가능하다고 판정한다:

| 관찰 상태 | 판정 |
|----------|------|
| spec 없음 | P1 미시작 |
| spec 있음 + design/arch 없음 | **P2 미시작** (Phase 1 완료) |
| Phase 1 완료 + design/arch 있음 | P2 진행 중 |
| P2 arch 완료 + (WITH_UI인데 design/ui 누락) | **P2 미완** → UI 복원 |
| P2 arch 완료 + WITH_UI + design/ui 있음 + design/api 누락 | **P2 미완** → API 복원 |
| P2 모든 산출물 + 승인 기록 | P2 완료 |

**핵심 원칙**: "직전 Phase의 **모든** 필수 산출물이 존재하지 않으면 다음 Phase로 진입하지 않는다."

## 라벨 기반 상태 머신

```
PHASE1_UX_RESEARCH_DONE → PHASE1_SPEC_DRAFT → PHASE1_BLOCKER_CHECK_PASS → PHASE1_USER_APPROVED
→ PHASE2_START → PHASE2_WORKTREE_CREATED → PHASE2_ARCH_STRUCTURE_DONE → PHASE2_ARCH_USER_APPROVED
→ PHASE2_UI_DESIGN_COMPLETE (WITH_UI만)
→ PHASE2_API_DESIGN_COMPLETE → PHASE2_FINAL_APPROVED
```

라벨은 **전진만 가능**. 스펙 변경 정책에서만 롤백 허용.

> **참고:** Phase 2-B (UI 디자인) 는 단계 3 이후 `teach-impeccable → ia-designer → 브리프 → iteration 루프 → 디테일 강화` 로 대폭 확장될 예정. 현재는 단순 `ui-designer` 디스패치 → `PHASE2_UI_DESIGN_COMPLETE`.

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
1. **리드가 직접 Write/Edit로 파일을 대신 생성하지 않는다**
2. **해당 에이전트를 재디스패치한다** (최대 3회) — "파일이 생성되지 않았다. Write 툴로 {경로}에 직접 저장하라"를 프롬프트에 명시
3. 3회 재디스패치 후에도 실패 시 사용자 에스컬레이션

## 에이전트 목록

| 모델 | 용도 | 비용 |
|------|------|------|
| **opus** | 아키텍처 결정, 설계 판단 | 10x |
| **sonnet** | 요구사항 분석, spec 작성 | 3x |
| **haiku** | 패턴 매칭, 단순 판단 | 1x |

| 에이전트 | Phase | 모델 | 역할 |
|---------|-------|------|------|
| `ux-researcher` | 1 | sonnet | 사용자 요구사항 분석 + spec 작성 |
| `blocker-checker` | 1 | haiku | spec 블로커 탐지 |
| `webapp-architect` | 2-A | opus | 웹 앱 아키텍처 결정 |
| `flutter-architect` | 2-A | opus | Flutter 앱 아키텍처 결정 |
| `native-architect` | 2-A | opus | Rust/C++ 네이티브 아키텍처 결정 |
| `ui-designer` | 2-B | opus | UI/UX 명세 + 시각 디자인 브리프 |
| `api-designer` | 2-C | opus | API 계약 정의 |
| `architect-reviewer` | 2 | opus | 설계 정합성 검증 |

> **단계 3 이후 추가**: `ia-designer` (opus) — Phase 2-B 의 IA/플로우 전담

---

## Phase 1: Spec

spec-design 리드는 직접 spec을 작성하지 않는다. 에이전트에 위임한다.

### 프로세스

1. 기존 spec 확인 (`docs/spec-design/spec/` 스캔)
2. `ux-researcher` → 사용자 요구사항 분석 + spec 작성 (플랫폼/스택 명시 포함)
3. `blocker-checker` 1차 디스패치 → 플랫폼/스택 미확정 여부 우선 확인
   - BLOCKED(플랫폼/스택 미확정) → 사용자 확인 후 spec 보완 → 재검사
4. spec 저장 → `blocker-checker` 2차 디스패치 (전체 블로커 검사)
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

spec-design 리드는 직접 설계를 작성하지 않는다. [webapp/flutter/native]-architect + ui-designer + api-designer + architect-reviewer 협업.
설계 산출물 = 아키텍처(arch), 사용자 인터페이스(ui, WITH_UI 모드만), API 계약(api).

### Phase 2 진입: worktree 격리 (필수)

Phase 2 프로세스 시작 전에 worktree를 생성한다. 이후 **Phase 2의 모든 작업은 worktree 내에서 수행**한다.

1. `Skill(git-worktree, {feature-name})` 호출 — `./worktrees/{feature-name}` 경로에 worktree + `feat/{feature-name}` 브랜치 생성
2. 이후 모든 에이전트 디스패치 시 **worktree 절대 경로**를 프롬프트에 반드시 주입한다
3. `.gitignore`에 `worktrees/` 포함 확인 (없으면 추가)
4. worktree 경로 예시: `/Users/moon/Workspace/money_track/worktrees/money-track-mvp`

→ PHASE2_WORKTREE_CREATED

> **중요:** 에이전트가 파일을 생성할 때 메인 경로가 아닌 **worktree 경로** 아래에 저장해야 한다. 리드는 디스패치 프롬프트에 worktree 절대 경로를 항상 포함하고, "이 경로 아래에 파일을 저장하라"고 명시한다.

### Phase 2 진입 전 검증 (필수)

| # | 체크 | 실패 시 조치 |
|---|------|------|
| 1 | `docs/spec-design/spec/{YYYY-MM-DD}-{feature}.md` 존재 | **Phase 1로 롤백** — `ux-researcher` 디스패치 |
| 2 | spec 말미에 blocker-check PASS 마크 또는 이전 세션 승인 기록 | `blocker-checker` 재실행 |
| 3 | Phase 1 사용자 승인 게이트 통과 기록 | 사용자 승인 요청 |
| 4 | worktree 생성 완료 (Phase 2 진입과 동시) | `Skill(git-worktree)` 호출 |

### 설계 모드 판정

`init_pipeline` 의 mode 인자로 결정:

| 모드 | 의미 | 단계 |
|------|------|------|
| `WITH_UI` | UI가 있는 기능 (프론트엔드 포함) | arch → ui → api |
| `WITHOUT_UI` | 순수 백엔드/라이브러리 | arch → api |

### Architect 선택 기준

프로젝트 파일 → spec 키워드 순서로 판정한다.

| 신호 | Architect |
|------|-----------|
| `pubspec.yaml` 존재 / spec에 Flutter·Dart 언급 | `flutter-architect` |
| `Cargo.toml` / `CMakeLists.txt` 존재 / spec에 Rust·C++ 언급 | `native-architect` |
| `package.json` 존재 / spec에 React·Vue·Next·웹 언급 | `webapp-architect` |
| 판정 불가 | 사용자에게 확인 후 dispatch |

### WITHOUT_UI 모드

1. Architect 선택 기준으로 프로젝트 타입 판정 → 해당 architect 디스패치
2. `architect-reviewer` 디스패치 (평가) → Critical이면 수정 후 재평가
3. 사용자 아키텍처 승인 게이트 → PHASE2_ARCH_USER_APPROVED
4. `api-designer` 디스패치 (UI 없이 spec + arch 만 입력)
5. `architect-reviewer` → API 리뷰 → 사용자 승인
6. → PHASE2_FINAL_APPROVED

### WITH_UI 모드 (순차)

```
1. [Architect 선택 기준으로 판정한 architect] → 아키텍처 설계
   (레이어 구조, 폴더 구조, 컴포넌트 경계, 기술 제약사항)
   → design/arch/ 저장
   → architect-reviewer 리뷰 → 수정 → 재리뷰 (PASS까지 반복)
   → PHASE2_ARCH_STRUCTURE_DONE

2. [사용자 아키텍처 승인 게이트]
   아키텍처 구조 요약 제시 → 사용자 확인
   피드백 있으면 architect 재디스패치 후 재검토
   → PHASE2_ARCH_USER_APPROVED

3. ui-designer → UX 명세
   ※ 단계 3 이후: teach-impeccable → ia-designer → 시각 도구 브리프(Claude Design/Stitch)
   → 산출물: design/ui/ + DESIGN.md
   → architect-reviewer → UI 명세 리뷰 → 수정 → PASS
   → [사용자 UI 피드백] → 반영
   → PHASE2_UI_DESIGN_COMPLETE

4. api-designer (UI 명세 필수 입력) → UI 에서 도출된 데이터 요구사항 + arch 기반 API/데이터 계약 설계
   → design/api/ 저장
   → architect-reviewer → API 명세 리뷰 → 수정 → PASS
   → [사용자 API 피드백] → 반영
   → PHASE2_API_DESIGN_COMPLETE

5. [사용자 최종 설계 승인] → PHASE2_FINAL_APPROVED
```

### 아키텍처 문서 템플릿

아키텍처 문서(`docs/spec-design/design/arch/{YYYY-MM-DD}-{feature}.md`)는 architect가 작성한다.

```markdown
# {Feature Name} — 아키텍처

## 레이어 구조
(Presentation / Domain / Data / Platform 등)

## 폴더 구조
모듈/기능 단위 디렉토리 경계만 정의한다. 특정 파일명은 구현 단계에서 결정.

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

## 컴포넌트 경계
주요 컴포넌트와 책임 범위

## 기술 스택 & 제약사항
비기능 요구사항, 성능, 보안, 기술 스택 제한 등
```

---

## 게이트 정책

| 전환 | 게이트 |
|------|--------|
| Phase 1 → 2 | spec + blocker-checker PASS + 사용자 승인 |
| Phase 2 모드 | `init_pipeline` 의 mode 인자로 결정 (WITH_UI / WITHOUT_UI) |
| 아키텍처 승인 | arch 문서 + 사용자 승인 |
| UI 승인 (WITH_UI만) | UI 명세 + 사용자 승인 |
| API 승인 | API 계약 + 사용자 승인 |
| Phase 2 최종 | 전 산출물 + 최종 승인 |

## 스펙 변경 정책

Phase 2 도중 spec 수정 필요 시: Phase 1로 롤백 → spec 수정 → blocker-checker 재실행 → 승인 → Phase 2 재개 (변경 영향 받는 문서만 재작성).

## 멀티 feature / 하위 호환성

- 각 feature는 독립 worktree + 독립 문서. 동시 진행 가능.
- `WITHOUT_UI` 모드가 기본 가정. UI가 명시되면 `WITH_UI`.
