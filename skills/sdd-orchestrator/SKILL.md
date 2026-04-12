---
name: sdd-orchestrator
description: SDD Phase 4의 멀티 에이전트 오케스트레이션. ORCHESTRATOR_STATE.md를 읽고, Wave별로 Agent 도구를 사용해서 Engineer → Reviewer → Test Automator 루프를 자동 실행한다.
model: opus
allowed-tools: Bash Read Write Edit Glob Grep Agent
user-invocable: false
---

<CRITICAL>
1. ORCHESTRATOR_STATE.md를 반드시 매 단계마다 갱신한다 — 생략 시 재개 불가
2. Agent 도구로만 Engineer/Reviewer/Test를 디스패치한다 — 코드 직접 작성 금지
3. Wave 내 동시 Agent 수는 최대 4개 — 초과 시 완료된 슬롯에 배정
4. 모든 태스크는 구현→리뷰→테스트 루프를 거친다 — 생략 금지
5. **context 90% 이상이면 현재 Wave 완료 후 즉시 상태 저장 + 스냅샷 커밋 + `PAUSED_AT_LIMIT` 전환 후 중단한다.** 리밋 감지 시에도 동일하게 상태 저장 후 중단한다 — 무시하고 계속하지 않는다
</CRITICAL>

# SDD Phase 4 Orchestrator

Phase 3(Plan)에서 생성된 ORCHESTRATOR_STATE.md와 task 문서를 입력으로 받아, Wave별 구현→리뷰→테스트 루프를 자동 실행한다.

## 사용법

```
/sdd-orchestrator <ORCHESTRATOR_STATE.md 경로>
/sdd-orchestrator resume
```

## 진입 조건

- ORCHESTRATOR_STATE.md가 존재하고 Wave 구성이 완료된 상태
- task 문서가 생성된 상태
- worktree가 생성된 상태

---

## Step 1: 초기화

1. ORCHESTRATOR_STATE.md를 Read로 읽기
2. **팀 배정 확인**: 팀 배정 섹션이 있으면 내 팀 번호와 담당 Wave 범위를 파악한다
   - 팀 배정 섹션 없음 → 전체 Wave 처리 (기존 단일 오케스트레이터 모드)
   - 팀 배정 섹션 있음 → 내 팀의 담당 Wave만 처리
3. 상태를 EXECUTING으로 변경 (내 팀 섹션만)
4. Wave 구성과 태스크 목록을 파악 (담당 Wave 범위만 필터링)
5. [agent-dispatch-guide.md](references/agent-dispatch-guide.md)를 참조하여 디스패치 준비

---

## Step 2: Wave 실행

### 상태 관리 원칙

**ORCHESTRATOR_STATE.md는 오케스트레이터만 쓴다.**
Worker(Engineer/Reviewer/Test)는 결과만 반환하고 state 파일에 접근하지 않는다.
오케스트레이터가 결과를 수신한 뒤 직접 갱신한다. 이렇게 해야 동시 쓰기 충돌이 없다.

### 실행 흐름

```
# 1. Wave 내 태스크를 병렬 디스패치 (최대 4개)
Agent(T-1, run_in_background: true)
Agent(T-2, run_in_background: true)
Agent(T-3, run_in_background: true)

# 2. 각 완료 결과를 수신 (Agent 툴이 완료 시 자동 반환)
← T-2: "DONE | 변경파일 목록"
← T-1: "DONE | 변경파일 목록"
← T-3: "BLOCKED | P1 잔존 내용"

# 3. 태스크별 루프: compliance → review → test
#    (수신 즉시 오케스트레이터가 STATE 갱신 후 다음 단계 디스패치)
# 4. Wave 내 전체 complete/escalated → 다음 Wave
```

5개 이상인 Wave는 4개 먼저 디스패치 → 완료 수신 시마다 다음 태스크 배정.

### 2.1 Engineer 디스패치

디스패치 전에 반드시 state를 먼저 갱신한다. 세션이 중단되더라도 재개 지점을 알 수 있어야 한다.

```
# 순서 엄수
1. ORCHESTRATOR_STATE.md: T-N → IN_PROGRESS (implementing)
2. Agent(
     subagent_type: task 문서의 구현자에 맞는 타입,
     prompt: task 문서 경로 + design/arch 문서 경로 + design/ui + design/api + 소유 파일 + 요구사항,
     run_in_background: true
   )
3. 결과 수신 후 ORCHESTRATOR_STATE.md: T-N → 결과 반영
```

Engineer는 작업 완료 후 결과만 반환한다. ORCHESTRATOR_STATE.md 수정 금지.

### 2.2 스펙 준수 확인

Engineer 결과 수신 → T-N: verifying 갱신 → Compliance Checker 디스패치:

```
Agent(subagent_type: "sdd-compliance-checker", prompt: spec 경로 + design/arch 경로 + design/ui + design/api + 변경 파일 목록)
```

- **PASS** → 오케스트레이터가 state 갱신 → 리뷰 단계로
- **FAIL** → 오케스트레이터가 누락 항목 포함 + state 갱신 → Engineer 재디스패치 (iteration +1)

compliance-checker는 "구현됐는가"를 확인한다. "잘 됐는가"는 Reviewer 몫이다.

### 2.3 리뷰

Compliance 결과 수신 → T-N: reviewing 갱신 → Reviewer 디스패치:

```
Agent(subagent_type: "sdd-reviewer", prompt: 리뷰 요청)
```

- **REVIEW_PASS** → 오케스트레이터가 state 갱신 → 테스트 단계로
- **REVIEW_FAIL** → 오케스트레이터가 피드백 누적 + state 갱신 → Engineer 재디스패치 (iteration +1)

### 2.4 테스트

Reviewer 결과 수신 → T-N: testing 갱신 → Test Automator 디스패치:

```
Agent(subagent_type: "sdd-test-automator", prompt: 검증 요청)
```

- **TEST_PASS** → 오케스트레이터가 해당 태스크 `complete` 갱신
- **TEST_FAIL** → iteration 확인:
  - < 3: 오케스트레이터가 이전 피드백 누적 + state 갱신 → Engineer 재디스패치
  - >= 3: 오케스트레이터가 `escalated` 갱신 → 사용자 에스컬레이션

### 2.5 Wave 완료 판정

현재 Wave의 모든 태스크가 `complete` 또는 `escalated`이면:
- escalated 없음 → 다음 Wave 시작
- escalated 있음 → 사용자에게 알리고 지시 대기

---

## Step 3: 통합 검증

모든 Wave 완료 후:
1. 전체 프로젝트 빌드 + 정적 분석
2. 모든 테스트 실행
3. compliance check (spec 요구사항 대조)
4. 실패 시 → 해당 태스크 Engineer에게 수정 요청

---

## Step 4: 완료 처리

1. result 문서 생성: `docs/sdd/result/{date}-{feature}.md`
2. ORCHESTRATOR_STATE.md 상태를 COMPLETED로 변경
3. 사용자에게 결과 보고
4. 사용자 승인 후 main 머지 + worktree 정리

---

## 리밋/에러 감지

- Agent가 리밋 관련 에러 반환 → 해당 태스크 interrupted
- **연속 2개 Agent 실패** → 전체 리밋 판정:
  - 남은 디스패치 보류
  - ORCHESTRATOR_STATE.md에 현재 상태 저장
  - 상태를 PAUSED_AT_LIMIT으로 변경
  - 사용자에게 알림

---

## 재개 프로토콜

`/sdd-orchestrator resume`:

1. ORCHESTRATOR_STATE.md 읽기
2. 상태 확인 (PAUSED_AT_LIMIT 또는 EXECUTING)
3. `git diff --stat` + `git log --oneline -10`으로 코드 상태 확인
4. 미완료 태스크만 Agent 재디스패치
5. "리밋 시 마지막 상태" 섹션의 Agent 응답 요약을 컨텍스트로 전달

---

## 에스컬레이션

사용자에게 알리는 상황:
- 태스크 3회 반복 실패 (escalated)
- 전체 리밋 도달
- 예상치 못한 에러 (빌드 실패 등)

---

## 참조

- 상태 파일 스키마: [state-schema.md](references/state-schema.md)
- Agent 디스패치 가이드: [agent-dispatch-guide.md](references/agent-dispatch-guide.md)
