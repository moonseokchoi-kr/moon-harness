# Moon Harness 멀티 에이전트 설계 이력

> **⚠️ 이 문서는 설계 당시 계획을 기록한 이력 문서입니다. 현재 구현의 Source of Truth가 아닙니다.**
> 현재 구현 상태는 아래 SOT를 참조하세요:
> - **SDD 전체 흐름**: `skills/sdd/SKILL.md`
> - **Phase 4 오케스트레이션**: `skills/sdd-orchestrator/SKILL.md`
> - **상태 스키마**: `skills/sdd-orchestrator/references/state-schema.md`
> - **에이전트 목록**: `skills/sdd/SKILL.md` 의 "에이전트 목록" 섹션
>
> 2026-04-08 Discord 논의 기반 정리. 이후 3차 실전 테스트(2026-04-09)와 중복 정리(2026-04-10)를 거쳐 실제 구현은 SOT 파일들로 이관됨.

## 0. 확정된 설계 결정

| 항목 | 결정 | 근거 |
|------|------|------|
| E2E 흐름 | 자동 라우팅 + 수동 전환 | 아이디어/구현은 분리하되, 스킬 선택은 자동화 |
| 세션 간 학습 | gstack 방식 (/learn, 사용자 피드백만 기록) | AI는 자기 실수를 인지 못함, 사용자 지적만 가치 있음 |
| 리밋 복구 | Opus 오케스트레이터 + Watchdog 셸 | Opus 판단력 포기 불가, 셸이 리밋 면역 보장 |
| 오케스트레이터 모델 | Opus | 판단/디스패치가 핵심 역할, 성능 타협 불가 |
| 검증 방식 | compliance-checker + reviewer 자동 호출 | "했다고 보고했지만 안 한" 문제 방지 |

## 1. 현재 상태

### 보유 자산
| 항목 | 수량 | 상태 |
|------|------|------|
| 스킬 | 10개 | brain-storm, idea-reframe, deep-idea, idea-workshop, sdd, sdd-taskrunner, harness, handoff, git-worktree, adversarial-review |
| SDD 에이전트 | 22개 | api-designer, architect-reviewer, blocker-checker, compliance-checker, context-manager, 언어별 engineer x10, implementer, taskmaster, test-automator, reviewer, ui-designer, performance-engineer, react-specialist, vue-engineer, sql-engineer |
| 훅 | 6개 | 보안 3개 (secret/dangerous/sensitive) + cmux 3개 (session-start/end/task-progress) |

### 핵심 문제점
1. **메인 컨트롤러 없음** — 사용자가 직접 Wave 디스패치, 에이전트 스폰, 결과 취합
2. **파일 충돌 방지 없음** — 여러 에이전트가 같은 파일 편집 가능
3. **에이전트 간 상태 공유 없음** — 공유 파일/큐 미정의
4. **리뷰어/테스트 미호출** — engineer가 구현+커밋하고 끝 (품질 게이트 부재)
5. **스톨/리밋 자동 복구 없음** — 수동 개입 필요 (money-track 사례)
6. **세션 간 학습 훅 미구현** — 설계만 완료, 실제 훅 없음

---

## 2. 참고 프로젝트 분석 요약

### gstack (garrytan/gstack)
- **차용할 점**: `/freeze` 파일 편집 범위 잠금, `/autoplan` 자동 체이닝, JSONL 학습 저장소, worktree 병렬
- **차용하지 않을 점**: 브라우저 데몬 (우리는 cmux 사용), MCP 배제 철학

### ECC (everything-claude-code)
- **차용할 점**: Ralphinho DAG (의존성 기반 자동 스케줄링), Loop Operator (스톨 감지), De-sloppify (품질 검증), SHARED_TASK_NOTES 패턴
- **차용하지 않을 점**: 181개 스킬 규모 (우리는 "더 적게, 더 단단하게"), 런타임 없는 패턴 문서 방식

### Claude Code Agent Teams (공식)
- **차용할 점**: TaskCompleted 훅 (품질 게이트), 공유 태스크 리스트, 의존성 자동 관리
- **차용하지 않을 점**: 네이티브 팀 의존 (토큰 3-4배, 세션 재개 불가, 팀 1개 제한)

---

## 3. 설계 목표

### 핵심 원칙
- **cmux 기반**: CC Teams 네이티브 대신 cmux로 멀티 에이전트 인프라 구축
- **메인 오케스트레이터**: 단일 컨트롤러가 모든 에이전트를 관리
- **구현→리뷰→수정→검증 루프**: 품질 게이트 내장
- **자동 복구**: 스톨/리밋 감지 시 자동 대응
- **재개 가능**: 어떤 시점에 중단되어도 상태 파일로 재개

---

## 4. 아키텍처

### 4.1 레이아웃 (cmux)

```
┌──────────────────┬──────────┬──────────┐
│                  │  Eng 1   │  Eng 2   │
│                  │          │          │
│   Main           ├──────────┼──────────┤
│   Orchestrator   │  Eng 3   │  Eng 4   │
│                  │          │          │
│                  ├──────────┴──────────┤
│                  │    Reviewer (공유)   │
│                  ├─────────────────────┤
│                  │  Test Automator     │
└──────────────────┴─────────────────────┘
```

- **왼쪽**: 메인 오케스트레이터 (항상 살아있음)
- **오른쪽 상단**: Engineer 에이전트들 (Wave별 그리드 배치)
- **오른쪽 하단**: Reviewer + Test Automator (공유, 순차 처리)

### 4.2 태스크 생명주기

```
1. Orchestrator → Engineer 할당
       ↓
  ┌─→ 2. Engineer 구현
  │       ↓
  │   3. Reviewer 리뷰
  │       ↓
  │   4. Engineer 수정 (피드백 반영)
  │       ↓
  │   5. Test Automator 검증
  │       ↓
  │   통과? ─── Yes → ✅ 완료 → 다음 Wave
  │     │
  │     No
  │     │
  └─────┘  (2→3→4→5 반복, 최대 3회)
  
  3회 실패 → 사용자 에스컬레이션 (Discord 알림)
```

### 4.3 오케스트레이터 동작 흐름

```
Phase 3 시작
    ↓
1. develop 문서 파싱 → 태스크 테이블 추출
    ↓
2. 의존성 분석 → DAG 구성 → Wave 자동 생성
    ↓
3. Wave N 시작:
   a. cmux로 Engineer pane 생성 (그리드 배치)
   b. 각 pane에 claude -p "태스크 프롬프트" 전송
   c. 감시 루프 진입:
      - 매 2분: read-screen으로 상태 수집
      - Engineer 완료 감지 → Reviewer pane에 리뷰 요청
      - Reviewer 완료 감지 → 피드백 있으면 Engineer에게 재전달
      - 리뷰 통과 → Test Automator에게 검증 요청
      - 테스트 통과 → 태스크 완료 마킹
      - 테스트 실패 → iteration +1, 2→3→4→5 반복
      - 스톨 감지 (5분 무응답) → 재시도 or 에스컬레이션
      - 리밋 감지 → 남은 태스크 저장, 리셋 시간 예약
    ↓
4. Wave N 전체 완료 → Wave N+1 시작 (3으로 돌아감)
    ↓
5. 전체 Wave 완료 → 통합 검증 → result 문서 생성
```

### 4.4 상태 파일 (재개 가능)

파일: `.claude/shared/ORCHESTRATOR_STATE.md`

```markdown
## Phase 3 상태
- develop 문서: docs/sdd/develop/2026-04-06-money-track-mvp.md
- 현재 Wave: 3
- 시작 시각: 2026-04-08T01:00:00+09:00

## 태스크 상태
| ID | Wave | Status | Iteration | Engineer Surface | 비고 |
|----|------|--------|-----------|-----------------|------|
| T-3 | 3 | complete | 1 | - | |
| T-4 | 3 | reviewing | 1 | surface:5 | |
| T-5 | 3 | testing | 2 | surface:6 | 1회차: 타입 불일치 |
| T-6 | 3 | implementing | 1 | surface:7 | |

## 이력
- [01:05] T-3 구현 완료 → 리뷰 통과 → 테스트 통과
- [01:12] T-5 구현 완료 → 리뷰 피드백: "타입 불일치" → 재구현 중
```

### 4.5 파일 소유권 관리

develop 문서의 폴더 구조 섹션에서 파일 소유권 파싱:

```markdown
## 폴더 구조
- lib/models/ (T-3) (NEW)
- lib/repositories/ (T-4, T-5) (NEW)
- lib/services/budget_calculator.dart (T-8) (NEW)
```

→ PreToolUse 훅으로 **다른 태스크의 파일 편집 차단** (gstack /freeze 방식)

---

## 5. 신규 필요 컴포넌트

### 5.1 sdd-orchestrator (신규 스킬)
- **역할**: Phase 3 전체 오케스트레이션
- **모델**: opus (설계/판단이 핵심)
- **기능**:
  - develop 문서 파싱 → DAG/Wave 자동 생성
  - cmux로 Engineer/Reviewer/Test pane 생성 및 관리
  - 감시 루프 (read-screen 기반 상태 수집)
  - 태스크 생명주기 관리 (구현→리뷰→수정→검증 루프)
  - 스톨/리밋 자동 감지 및 복구
  - 에스컬레이션 (Discord 알림 가능)
  - 상태 파일 기록 (재개 가능)
  - result 문서 생성

### 5.2 파일 잠금 훅 (신규 훅)
- **역할**: 태스크별 파일 소유권 강제
- **트리거**: PreToolUse (Edit, Write)
- **동작**: ORCHESTRATOR_STATE.md의 파일 소유권 확인 → 범위 밖 편집 차단

### 5.3 태스크 완료 훅 (신규 훅)
- **역할**: 품질 게이트
- **트리거**: Engineer 커밋 감지 시
- **동작**: lint/analyze/test 자동 실행 → 실패 시 오케스트레이터에 알림

### 5.4 SHARED_NOTES.md (신규 공유 파일)
- **역할**: 에이전트 간 컨텍스트 공유
- **내용**: 공유 타입 정의, API 계약, 이전 태스크 결과 요약
- **위치**: `.claude/shared/SHARED_NOTES.md`

---

## 6. 기존 컴포넌트 수정

### 6.1 sdd-reviewer (역할 강화)
- 현재: 정의만 되어있고 호출 안 됨
- 변경: 오케스트레이터가 Engineer 완료 후 자동 호출
- 입력: 변경된 파일 목록 + diff
- 출력: 승인 or 피드백 (구체적 수정 요청)

### 6.2 sdd-test-automator (역할 강화)
- 현재: TDD 테스트 작성 전용
- 변경: 리뷰 통과 후 통합 검증 역할 추가
- 입력: 태스크 범위의 테스트 대상
- 출력: 통과 or 실패 (실패 원인 + 재현 방법)

### 6.3 SDD SKILL.md (Phase 3 흐름 변경)
- 현재: taskmaster → engineer 병렬 → 끝
- 변경: orchestrator → (engineer → reviewer → engineer → test) 루프 → result

### 6.4 develop 템플릿 (파일 소유권 추가)
- 태스크 테이블에 "소유 파일" 컬럼 추가
- 또는 폴더 구조 섹션에서 (T-N) 태그로 소유권 명시

---

## 7. 비교: Before vs After

### Before (money-track 방식)
```
사용자 "Phase 3 시작해"
  → Claude가 즉석에서 Wave 구성
  → Engineer 에이전트 병렬 스폰
  → 리뷰 없이 커밋
  → 리밋 걸리면 멈춤
  → 사용자가 수동 재개
  → 통합 검증도 수동
```

### After (sdd-orchestrator)
```
사용자 "/sdd phase3"
  → orchestrator가 develop 파싱 → DAG → Wave 자동 생성
  → cmux 그리드로 Engineer 배치
  → 구현 완료 → Reviewer 자동 호출
  → 피드백 → Engineer 자동 수정
  → 리뷰 통과 → Test 자동 검증
  → 실패 → 2→3→4→5 반복 (최대 3회)
  → 리밋 → 상태 저장 + 리셋 후 자동 재개
  → 전체 완료 → result 문서 자동 생성
```

---

## 8. 구현 우선순위

3개 트랙으로 분류: 워크플로우 컨트롤러, 멀티 에이전트 오케스트레이터, 학습 시스템.

### Track A: 워크플로우 컨트롤러 (harness 전체 흐름)

사용자의 자연어 요청을 파악해서 적절한 스킬로 자동 라우팅하고,
스킬 간 전환을 자연스럽게 연결하는 메인 컨트롤러.

| 순서 | 항목 | 방법 | 난이도 | 상태 |
|------|------|------|--------|------|
| A-1 | harness-controller 스킬 생성 | skill-creator | 중 | ✅ 완료 |
| A-2 | 기존 스킬 체이닝 수정 (brain-storm→sdd 연결 등) | 직접 수정 | 중 | ✅ 완료 |
| A-3 | 스킬 description 트리거 최적화 | skill-creator | 중 | 미구현 |
| A-4 | 테스트 + 트리거 정확도 튜닝 | - | 상 | 미구현 |

**harness-controller 역할:**
- 모든 개발 관련 대화에서 자동 활성화 (`user-invocable: false`)
- 의도 파싱 → 적절한 스킬 라우팅 (superpowers의 using-superpowers 패턴)
- 스킬 확인을 강제 ("관련 스킬이 있는지 먼저 확인")

**스킬 체이닝 수정:**
- brain-storm: 완료 시 → "구현하려면 /sdd를 안내"
- deep-idea: 졸업 시 → "구현하려면 /sdd를 안내"
- sdd Phase 2 완료 → "Phase 3는 /sdd-orchestrator 호출"
- sdd-orchestrator 완료 → "배포는 Phase 4 안내"

### Track B: 멀티 에이전트 오케스트레이터 (SDD Phase 3)

cmux 기반으로 Engineer/Reviewer/Test 에이전트를 자동 관리하고,
구현→리뷰→수정→검증 루프를 자동 실행하는 Phase 3 전용 오케스트레이터.

| 순서 | 항목 | 방법 | 난이도 | 상태 |
|------|------|------|--------|------|
| B-1 | ORCHESTRATOR_STATE.md 스키마 정의 | 직접 작성 | 하 | ✅ 완료 |
| B-2 | sdd-orchestrator 스킬 생성 | skill-creator | 중 | ✅ 완료 |
| B-3 | on-rate-limit.sh (StopFailure 훅) | 직접 작성 | 중 | ✅ 완료 |
| B-4 | file-ownership.sh (PreToolUse 훅) | 직접 작성 | 중 | ✅ 완료 |
| B-5 | setup.sh에 훅 자동 등록 추가 | 직접 수정 | 중 | ✅ 완료 |
| B-6 | 기존 SDD SKILL.md Phase 3 흐름 수정 | 직접 수정 | 중 | ✅ 완료 |
| B-7 | 실전 테스트 (실제 프로젝트로 Phase 3 실행) | - | 상 | 미구현 |
| B-8 | 테스트 결과 기반 SKILL.md 튜닝 | 직접 수정 | 중 | 미구현 |

### Track C: 학습 시스템

사용자 피드백을 기록하고 다음 세션에 주입하는 학습 도구.

| 순서 | 항목 | 방법 | 난이도 | 상태 |
|------|------|------|--------|------|
| C-1 | /learn 스킬 (gstack 방식) | skill-creator | 중 | 미구현 |
| C-2 | pitfalls.md 자동 주입 (SessionStart 훅) | 직접 작성 | 중 | 미구현 |
| C-3 | frequency 기반 CLAUDE.md 승격 로직 | 스킬 내 로직 | 중 | 미구현 |

### 실행 순서

```
Phase 1 — 기반 구축 (완료):
  B-1~B-6 ✅

Phase 2 — 워크플로우 컨트롤러:
  A-1 → A-2 → A-3 → A-4

Phase 3 — 통합 테스트:
  B-7 (실전 테스트) → B-8 (튜닝)
  A-4와 B-7을 병행 가능

Phase 4 — 학습 시스템:
  C-1 → C-2 → C-3

Phase 5 — 전체 E2E 테스트:
  아이디어 → brain-storm → sdd → orchestrator → 완료까지 관통 테스트
```

### 우선순위 근거

- **Track A가 Track B보다 먼저**: 컨트롤러 없이 오케스트레이터를 테스트하면, 사용자가 수동으로 /sdd-orchestrator를 호출해야 하는 기존 문제가 반복됨
- **Track C는 가장 나중**: 학습은 실제 사용 경험이 쌓인 후 더 효과적
- **Phase 3(통합 테스트)에서 A와 B를 함께 검증**: 실제 프로젝트로 전체 흐름 테스트

---

## 9. 추가 설계: 확정된 사항

### 9.1 E2E 흐름 — 자동 라우팅 + 수동 전환

```
사용자: "서버 트래픽 테스트 페이지 만들고 싶어"
  ↓ harness가 의도 파싱
  ↓ brain-storm 자동 시작
  ↓ 아이디어 완성
  ↓ 사용자: "이제 만들자" (수동 전환)
  ↓ sdd Phase 1 시작
  ↓ ... 이후 자동
```

- 단계 안에서는 자동 진행
- 단계 간 전환은 사용자 결정 (의도적 분리)
- 사용자가 스킬 이름을 몰라도 자연어로 시작 가능
- 구현 우선순위: 낮음 (멀티 에이전트 이후)

### 9.2 세션 간 학습 — gstack 방식 (/learn)

```
사용자: "이건 안티패턴이야, 이렇게 해"
  ↓ /learn 또는 "기억해"
  ↓ docs/pitfalls.md에 JSONL 기록:
    {"pattern":"riverpod-update","problem":"update 메서드명 충돌",
     "solution":"updateItem으로 변경","frequency":1}
```

- **AI 자동 추출 안 함** — AI는 자기 실수를 인지 못함
- 사용자가 지적할 때만 기록
- frequency 3 이상 → CLAUDE.md 핵심 규칙 승격
- `/learn search`, `/learn prune`으로 관리
- 빌드/테스트 실패는 "실수"가 아닌 "접근법 문제" → 학습 대상 아님

### 9.3 리밋 복구 — StopFailure 훅 + Watchdog 셸

**핵심 발견**: 리밋 도달 시 `Stop`이 아닌 `StopFailure` 훅이 트리거됨 (error_type: rate_limit)

```
정상: Opus 오케스트레이터 감시 루프
  ↓ 리밋 도달
  ↓ StopFailure 훅 자동 실행 (셸 — 토큰 불필요!)
  
StopFailure 훅 (on-rate-limit.sh):
  1. 각 pane 스크롤백 캡처 (cmux read-screen --scrollback --lines 500)
     → 사라지는 정보(세션 컨텍스트)만 저장
     → git diff는 재개 시 파악 가능하므로 저장 불필요
  2. ORCHESTRATOR_STATE.md에 기록
  3. Watchdog 예약 (nohup sleep + 재시작)
  
Watchdog:
  sleep until reset_time
  → cmux send --surface $ORCH_SURFACE
  → ".claude/shared/ORCHESTRATOR_STATE.md를 읽고 중단 지점부터 재개해"
  
새 오케스트레이터:
  1. ORCHESTRATOR_STATE.md 읽기 (경로만 전달, 직접 Read)
     → 각 Engineer가 뭘 하고 있었는지 (스크롤백)
     → 어떤 Wave/태스크가 미완료인지
  2. git diff/status로 코드 상태 확인
  3. 죽은 pane 정리 + 새 pane 생성
  4. 미완료 태스크만 새 Engineer에게 할당
     → "T-17 이어서. 이전 상태: [스크롤백에서 추출한 컨텍스트]"
  5. 정상 감시 루프 재진입
```

**settings.json 훅 설정:**
```json
{
  "hooks": {
    "StopFailure": [{
      "matcher": { "error_type": "rate_limit" },
      "hooks": [{
        "type": "command",
        "command": "~/.claude/hooks/on-rate-limit.sh"
      }]
    }]
  }
}
```

**재개 방식**: 상태 파일 경로만 프롬프트로 전달 → 새 세션이 직접 Read로 읽기

### 9.4 검증 강화 — compliance-checker 자동 호출

```
Engineer: "T-3 완료"
  ↓
Orchestrator: compliance-checker 호출
  - develop 문서의 T-3 요구사항 로드
  - 실제 파일 존재 여부 확인
  - analyze/lint 에러 0개 확인
  - 요구사항 체크리스트 대조
  ↓
불일치: "T-3 미완료. 누락: transaction_detail_sheet.dart"
  → Engineer에게 재작업 지시
```

---

## 10. 확정된 미결 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| Reviewer/Test pane | pane 상시 유지, Claude 세션은 태스크마다 새로 시작 | idle 토큰 방지 + pane 재사용 |
| worktree 격리 | 안 함 | 파일 소유권 훅으로 충돌 방지, 머지 복잡도 제거 |
| 동시 Engineer 수 | 4개 | API 사용량 적절, 시각적으로 그리드 적합 |
| 리밋 복구 pane | 새로 생성 | 죽은 세션 컨텍스트 없음, 깔끔한 재시작 |
| E2E 라우팅 | CLAUDE.md 규칙으로 시작, 추후 전용 스킬 | 멀티 에이전트보다 후순위, 테스트 환경 스킬 선행 필요 |
| 오케스트레이터 재개 | 상태 파일 경로를 프롬프트로 전달 → Read로 직접 읽기 | 단순하고 안정적 |

## 11. 아이디어 파이프라인 재설계 (후속 과제)

**문제 인식**: 현재 아이디어 단계 스킬들이 워터폴처럼 동작하지만, 실제로는 이터레이션이 필요하다. 구현 이전에 좋은 계획이 나와야 좋은 결과물이 나온다.

### 현재 (워터폴)
```
brain-storm → idea-reframe → deep-idea → sdd
```

### 필요한 구조 (이터레이션 루프)
```
┌→ brain-storm (발산 — 아이디어 생성)
│      ↓
│  idea-reframe (구체화 — 방향 잡기)
│      ↓
│  deep-idea (리서치 — 데이터 수집)
│      ↓
│  ??? 검증 스킬 (판단 — 이 아이디어가 될까?)
│      ↓
│  통과? ── Yes → sdd
│    │
│    No (피드백과 함께 재순환)
│    │
└────┘
```

### 해결해야 할 것

1. **검증 전용 스킬 신설** — deep-idea에서 리서치와 검증을 분리
   - 리서치: "시장 규모, 경쟁사, 기술 가능성" → 사실 수집
   - 검증: "치명적 결함은? 이 방향이 맞는지?" → 판단

2. **이터레이션 오케스트레이터** — idea-workshop을 Phase 3의 sdd-orchestrator처럼 루프 관리자로 강화
   - 각 단계 완료 감지 → 다음 단계 안내
   - 검증 실패 시 → 어느 단계로 돌아갈지 판단 (발산? 구체화? 리서치?)
   - 졸업 조건 자동 판별

3. **피드백 누적** — 이터레이션마다 이전 피드백을 다음 단계에 전달
   - Phase 3의 "리뷰 피드백 → Engineer 재전달"과 같은 패턴

### 우선순위

구현 단계(Track A, B)가 완료된 후 별도 트랙으로 진행. 하지만 **이 과제가 해결되지 않으면 harness의 전체 가치가 반감**된다. 좋은 구현 파이프라인이 있어도 입력(아이디어/계획)의 품질이 낮으면 결과물도 낮다.

## 12. 구현 준비 완료
