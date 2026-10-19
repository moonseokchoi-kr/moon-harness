---
name: sdd-orchestrator
description: SDD Phase 4의 멀티 에이전트 오케스트레이션. ORCHESTRATOR_STATE.md를 읽고, Wave별로 Agent 도구를 사용해서 Engineer → Reviewer → Test Automator 루프를 자동 실행한다.
model: opus
allowed-tools: Bash Read Write Edit Glob Grep Agent Skill
user-invocable: false
---

<CRITICAL>
1. ORCHESTRATOR_STATE.md를 반드시 매 단계마다 갱신한다 — 생략 시 재개 불가
2. Agent 도구로만 Engineer/Reviewer/Test를 디스패치한다 — 코드 직접 작성 금지
3. Wave 내 동시 Agent 수는 최대 4개 — 초과 시 완료된 슬롯에 배정
4. 모든 태스크는 구현→리뷰→테스트 루프를 거친다 — 생략 금지
5. **context 90% 이상이면 현재 Wave 완료 후 즉시 상태 저장 + 스냅샷 커밋 + `PAUSED_AT_LIMIT` 전환 후 중단한다.** 리밋 감지 시에도 동일하게 상태 저장 후 중단한다 — 무시하고 계속하지 않는다
6. **no-clean 규율**: Phase 4 전 구간에서 태스크 간 `clean`(빌드 캐시 삭제)을 금지한다. 워밍업 빌드 캐시를 보존해야 per-task 증분 빌드가 빠르다. Engineer/Test 디스패치 프롬프트에 "clean 금지, 증분 빌드만" 명시.
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
5. **빌드 프로파일 확보** — Phase 4 진입 시 오케스트레이터가 직접 확보한다. 인터프리터·툴의 경로는 하드코딩하지 않고 확정된 명령만 기록한다:
   1. STATE의 `## 빌드 프로파일`에 프로파일이 이미 있으면 재확보하지 않고 그대로 쓴다(이후 단계는 건너뛴다).
   2. 없으면 프로젝트 CLAUDE.md → CLAUDE.local.md 순서로 빌드·테스트 명령을 찾는다. CLAUDE.local.md는 worktree 경로를 먼저 읽고, 없으면 이어서 메인 repo 루트(`git rev-parse --git-common-dir`로 구함)를 읽는다.
   3. 거기에도 없으면 `/build-notes` 스킬을 `Skill(build-notes)`로 실행한다. 단 사용자 질문이 가능한 컨텍스트에서만 실행하고, 팀원 컨텍스트에서는 건너뛴다. build-notes는 사용자 전역 스킬이라 플러그인에 없을 수 있다(이관하지 않는다). Skill 호출이 없음/거부 오류면 실패로 보고 다음 단계로 진행한다. 성공하면 build-notes 결과는 `CLAUDE.local.md`에 기록되므로 그 내용을 STATE로 옮긴다.
   4. build-notes가 없거나 건너뛰었거나 실패했으면 사용자 질문으로 폴백해 빌드·테스트 명령을 확인한다(사용자 질문이 가능한 경우).
   5. 사용자 질문이 불가한 Agent Team 팀원(sdd-team-leader) 컨텍스트면 BLOCKED를 반환하고 STATE에 BLOCKED 사유를 기록한다. 팀 리드가 사용자에게 중계한다. 리드가 사용자 답을 재디스패치 프롬프트의 "빌드 프로파일 확정값"으로 넘기면, 오케스트레이터는 그 확정값을 STATE `## 빌드 프로파일`에 기록하고 진행한다(같은 BLOCKED 반복 금지).
   - 확보 결과는 메인 repo 루트 CLAUDE.local.md에 남겨 다음 사이클(사이클 간)에 재사용한다. worktree에만 생겼으면 메인 repo 루트로 반영(복사)한다.
   - 출처로 읽은 파일 경로를 STATE 빌드 프로파일 출처에 기록한다(확보한 파일 경로 포함).
   6. 확보한 프로파일을 STATE `## 빌드 프로파일`에 기록한다(출처 포함, 스키마: [state-schema.md](references/state-schema.md)).
6. **워밍업 빌드 (build-aware TDD, 1회)**:
   - 프로파일 유형이 `build-required`이고 `워밍업 완료`가 미기록이면 → 프로파일의 **워밍업 빌드 명령을 1회 실행**해 콜드 캐시를 데운다. 완료 후 STATE에 `워밍업 완료: <시각>` 기록(중복 방지).
   - `fast-scoped`이면 워밍업 생략하고 `워밍업 완료: 미실행(fast-scoped)` 기록.
   - 워밍업 빌드 실패 → 사용자 에스컬레이션(이후 per-task 빌드가 모두 실패하므로 진행 금지).
7. [agent-dispatch-guide.md](references/agent-dispatch-guide.md)를 참조하여 디스패치 준비

> 📌 build-aware TDD: 비싼 것은 콜드 캐시 빌드 1회뿐이다. 워밍업 이후 per-task는 **증분 빌드 + 스코프 테스트**로 RED/GREEN을 매 태스크 확인하고, 태스크 간 clean은 금지(no-clean)한다. 상세: `skills/sdd/SKILL.md` → "빌드 프로파일" 섹션.

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
     prompt: task 문서 경로 + spec 문서 경로 + 소유 파일 + 요구사항
             + **빌드 프로파일**(증분 빌드 + 이 태스크 스코프 테스트 명령, no-clean 규율),
     run_in_background: true
   )
3. 결과 수신 후 ORCHESTRATOR_STATE.md: T-N → 결과 반영
```

**테스트 스코프 연결**: task 문서에는 실행 명령이 없고 "테스트 스코프" 값만 있다. 오케스트레이터가 task 문서의 "테스트 스코프" 값을 읽어 빌드 프로파일 `테스트 실행` 명령의 `{filter}` 자리에 채운 완성 명령을 프롬프트에 넣는다(이 연결이 없으면 Engineer가 실행 명령을 만들 수 없다). 스코프가 여러 개이면 `{filter}`는 프로파일의 "테스트 필터 문법"에 따라 조합한다.
테스트 스코프가 비어 있으면 전체 실행으로 대체하지 않고 task 문서 오류로 보고하며 Engineer를 디스패치하지 않는다.

Engineer는 작업 완료 후 결과만 반환한다. ORCHESTRATOR_STATE.md 수정 금지.

### 2.2 스펙 준수 확인

Engineer 결과 수신 → T-N: verifying 갱신 → Compliance Checker 디스패치:

```
Agent(subagent_type: "sdd-compliance-checker", prompt: spec 단일 문서 경로 + 변경 파일 목록)
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
Agent(subagent_type: "sdd-test-automator",
      prompt: 검증 요청 + 빌드 프로파일(증분 빌드 + 이 태스크 스코프 테스트 명령, no-clean))
```

> 📌 테스트 단계 프롬프트도 동일하게, task 문서의 "테스트 스코프" 값을 빌드 프로파일 테스트 실행 명령의 `{filter}` 자리에 채워 완성 명령으로 전달한다.

> 📌 워밍업은 Step 1에서 1회 끝났다. Test Automator는 **증분 빌드 + 스코프 테스트**로 RED/GREEN을 확인한다 — "전체 테스트 1회 실행"으로 대체 금지.

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

모든 Wave 완료 후 (여기서만 전체 스위트를 돈다 — per-task verify는 스코프만 돌았다):
1. 전체 프로젝트 빌드(증분, no-clean) + 정적 분석 — 빌드 프로파일 명령 사용
2. 모든 테스트 실행 (전체 스위트)
3. compliance check (spec 요구사항 대조)
4. 실패 시 → 해당 태스크 Engineer에게 수정 요청

---

## Step 4: 완료 처리 (PR 기반 수렴)

main에 직접 머지하지 않는다. PR을 열고 외부 신호가 전부 green이 될 때까지 수렴시킨 뒤, **최종 머지는 사람이 승인**한다.

1. result 문서 생성: `docs/sdd/result/{date}-{feature}.md`
   - spec에 `## UI` 섹션이 있거나 task 문서 테스트 타입에 E2E/UI가 있으면 result 문서에 수동 테스트 시나리오를 기록한다(개발자가 직접 확인할 조작 순서·기대 결과).
   - 시나리오의 입력은 test-automator verify 보고의 "수동 테스트 시나리오" 필드이며, 오케스트레이터가 그 필드를 result 문서에 옮긴다(test-automator는 result 문서를 직접 쓰지 않음).
   - E2E 테스트는 개발자가 수동 확인 후 요청할 때만 작성한다.
2. ORCHESTRATOR_STATE.md 상태를 COMPLETED로 변경
3. **kompound 박제 실행** (F1, T-12) — `hooks/enforcement/stop-pipeline.py`의 완료 게이트가 이 시점 이후의 Stop 훅에서 자동으로 directive를 발화한다. directive 지시에 따라 kompound 박제 CLI(`python3 -m hooks.lib.kompound_snapshot apply --json`, 절대경로는 directive가 제시)를 실행하고, 성공/실패 결과를 사용자에게 보고한다. 실패해도 사이클을 되돌리지 않고 사용자 판단을 요청한다.
   - **근거(D1, 사용자 확정)**: 다음 4번(push + pr-converge)은 코드단 수정 작업이고, 박제 대상 문서(spec/arch/task/result)의 의도는 이미 2번(STATE=COMPLETED)에서 확정된다 — 이후 코드가 더 바뀌어도 박제할 문서 내용은 달라지지 않는다. 따라서 박제는 push 이전, STATE 확정 직후 실행하는 것이 안전하다.
   - 이 위치가 성립하려면 설계 전제 3가지가 모두 충족돼야 한다: ① result 문서가 이미 생성되어 있다(1번) ② worktree가 아직 살아 있다(6번 정리는 더 뒤) ③ self-improve(Step 5)보다 먼저 실행된다.
   - `.harness/LEARNING.md`에 이번 사이클 신규 엔트리가 있는지 여부와 **무관하게** 실행한다 — Step 5의 self-improve를 건너뛰어도 이 박제 스텝은 그대로 실행된다.
4. head 브랜치 push 후 `Skill(pr-converge)`로 PR을 열고 수렴 루프를 시작한다.
   - CI/CD·테스트·빌드·린트·**모든 리뷰 코멘트**에 대해 green까지 자동 수정·push.
   - 분 단위로 걸리는 CI를 블로킹하지 않도록, 사용자에게 **`/loop /pr-converge`로 주기 실행**을 안내한다 (CI 도는 중 ~270s, 사람 코멘트 대기 중 길게).
5. pr-converge가 **CONVERGED**(전부 green + 코멘트 처리 완료)를 보고하면 → 사용자에게 결과 + 머지 승인 요청. **NEEDS_HUMAN/BLOCKED**면 → 막힌 항목(설계 코멘트·반복 실패)을 사람에게 에스컬레이션.
6. 사용자 머지 승인 후 worktree 정리.
7. **ORCHESTRATOR_STATE.md 아카이브** — 결정적 글루를 호출한다(판정·이동·링크 갱신이 전부 결정적이므로 프롬프트가 판단하지 않는다):
   ```bash
   python3 skills/sdd-orchestrator/scripts/archive_state.py --json
   ```
   `docs/sdd/ORCHESTRATOR_STATE.md` → `docs/sdd/archive/{date}-{feature}-ORCHESTRATOR_STATE.md`로 `git mv`한다(추적 안 되면 일반 이동). `date`는 result 문서명에서 가져오므로 "정리를 언제 돌렸는가"가 아니라 "사이클이 언제 끝났는가"가 이름에 남는다.
   - **링크 교체 범위**: `docs/sdd/**`의 **마크다운 링크 타깃(`](...)`)만** 교체한다 — 그 형태는 문법적으로 항상 경로 참조라 모호성이 없다. 백틱 경로와 산문 언급은 **절대 교체하지 않고** `manual_refs`로 보고만 한다. 완전한 경로여도 그것이 *이 사이클 인스턴스*를 가리키는지 *SDD 규약 일반*을 서술하는지 스크립트가 판정할 수 없기 때문이다(예: "Phase 4는 `pipeline.json`이 아니라 `docs/sdd/ORCHESTRATOR_STATE.md`로 운영된다" — 아카이브 경로로 바꾸면 문장이 거짓이 된다). `manual_refs` 목록은 사용자에게 그대로 전달한다.
   - **왜 정리하는가**: STATE는 머지되면 main에 영구히 남는다. 그러면 ① 완료된 사이클이 현역처럼 보여 다음 사이클 STATE와 구분되지 않고 ② `hooks/enforcement/stop-pipeline.py`의 T1 완료 게이트가 STATE **존재**를 진입 조건으로 쓰기 때문에, SDD를 한 번이라도 완료한 프로젝트는 그 사이클과 무관한 이후 모든 세션의 모든 Stop 훅에서 판정 비용을 영구 지불한다(콜드 프로세스 실측 **+43.5ms**). 아카이브하면 `is_file()` 실패로 **패키지 import 이전에** 조기 반환하므로 그 비용이 사라진다.
   - **안전 인터록** — 스크립트가 아래 중 하나라도 걸리면 옮기지 않고 사유를 보고한다: 상태가 `COMPLETED`가 아님 / result 문서 부재 / **kompound 박제가 `PENDING`·`CATALOG_PENDING`·`FAILED`**. 마지막 항목이 핵심이다 — T1은 STATE 존재를 진입 조건으로 쓰므로, 미뤄진 박제를 남긴 채 아카이브하면 재시도가 **영구히 오지 않는다**(비수렴). 목적지가 이미 있으면 덮어쓰지 않고 no-op(멱등).
   - **T2 게이트(`hooks/enforcement/kompound-snapshot-gate.sh`)는 영향받지 않는다** — STATE 의존이 0건이고 명령만 보고 판정하므로, "워크트리 삭제 직전 미박제 문서 차단" 안전망은 그대로 살아 있다.
   - enforcement 훅 8개는 전부 STATE 부재를 통과(`exit 0`)로 처리하므로 아카이브가 게이트를 깨지 않는다. `hooks/lib/kompound_snapshot/scan.py`의 `SKIP_NAMES`에 `ORCHESTRATOR_STATE`가 있어 아카이브 사본이 새 박제 대상이 되지도 않는다.

> 📌 pr-converge는 SDD 밖에서도 독립 사용 가능하다 (`/pr-converge <pr>`). 자세한 분류·서킷브레이커·케이던스 규칙은 skills/pr-converge/SKILL.md 참조.

---

## Step 5: 자가개선 회고 (자동 트리거)

머지·정리 완료 후, 이번 사이클에서 `.harness/LEARNING.md`에 append된 교훈을 반영한다:

1. `.harness/LEARNING.md`에 이번 사이클 신규 엔트리가 있으면 → `Skill(self-improve)`를 호출한다.
2. 신규 엔트리가 없으면 건너뛴다.
3. self-improve가 보고한 결과(프로젝트 티어 자동 적용 N건 / 하네스 티어 제안 M건)를 사용자에게 함께 전달한다. 하네스 티어 제안이 있으면 `.harness/harness-proposals/`에 승인 대기 중임을 명시한다.

> 📌 회고가 실패하거나 건너뛰어도 사이클 완료에는 영향 없다. 사용자가 나중에 수동으로 `/self-improve`를 돌릴 수 있다.

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
