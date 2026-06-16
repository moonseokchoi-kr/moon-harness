---
name: pr-converge
description: "PR을 외부 객관 신호(CI/CD, 테스트, 빌드/린트, 모든 리뷰 코멘트)에 대해 green이 될 때까지 자동 수렴시키는 루프. 'PR 수렴', 'CI 고쳐', 'PR 마무리', 'pr-converge', '리뷰 코멘트 반영', '테스트 통과시켜' 맥락에서 호출. /loop로 주기 실행하도록 설계됨."
---

# PR Converge (외부 신호 수렴 루프)

PR을 던지고 사람에게 넘기는 대신, **CI/CD·테스트·빌드·린트·리뷰 코멘트**라는 외부 객관 신호에 대해 PR이 전부 green이 될 때까지 스스로 수렴시킨다.

```
PR 열기/확인 → [CI 상태 + 모든 코멘트 + 테스트] 관측 → 진단·분류
            → 수정 (해당 engineer 디스패치) → push → 재관측 → … → green → 완료
            막히면(동일 실패 N회 / 사람 판단 필요) → 에스컬레이션
```

## 핵심 원칙

- **/loop 1패스 구조.** CI는 분 단위로 걸린다. 길게 블로킹 폴링하지 않는다. **이 스킬 1회 호출 = 관측→수정 1패스**이고, `/loop`가 권장 간격으로 다시 깨운다. 매 패스 끝에 상태와 다음 간격을 보고한다.
- **객관 신호는 자동, 판단은 에스컬레이션.** CI/테스트/빌드/린트 실패는 green까지 자동 수정·push. 리뷰 코멘트는 *코드 수정 요청*만 자동 반영하고, *설계/토론/질문*은 사람에게 올린다.
- **모든 코멘트를 본다.** 공식 "Request changes" 리뷰 상태에 의존하지 않는다 (그 방식으로 리뷰가 안 들어옴). conversation 코멘트 + inline review 코멘트 + review 본문을 **리뷰 상태와 무관하게 전부** 수집해 분류한다. 무엇도 조용히 무시하지 않는다.
- **최종 머지는 사람.** 루프는 PR을 green + 모든 코멘트 처리 상태까지 가져간 뒤 **머지를 사람에게 요청**한다. 자동 머지하지 않는다.
- **안전한 push.** PR head 브랜치에만 push. main 직접 push·force-push 금지. 원격이 앞서가면 rebase/pull 후 진행.

## 사용법

```
/loop /pr-converge          # 권장 — 자동 주기 수렴
/pr-converge                # 1패스만 수동 실행 (현재 브랜치 PR 대상)
/pr-converge <pr-number>    # 특정 PR 대상
```

전제: `gh` CLI 인증됨 + 원격이 GitHub. (미인증/비-GitHub면 1패스에서 감지해 보고하고 종료.)

---

## 상태 파일

`.harness/pr-converge-state.json` — PR별 진행 상태. 코멘트 재처리 방지 + 서킷브레이커.

```json
{
  "schema_version": 1,
  "pr": 42,
  "branch": "feat/auth-flow",
  "processed_comment_ids": [10293, 10294],
  "fix_attempts": { "ci:unit-tests": 1, "comment:10293": 1 },
  "iterations": 3,
  "status": "WORKING",
  "last_tick_at": "2026-06-16T00:00:00Z",
  "escalations": []
}
```

없으면 1패스에서 생성. PR 머지/종료 시 사람이 정리하거나 다음 PR에서 덮어씀.

---

## 1패스 절차

### Step 0 — 전제 확인
- `gh auth status` 확인. 실패 → 보고 후 종료 (`status: BLOCKED`, 사유: gh 미인증).
- 현재 브랜치 PR 확인: `gh pr view --json number,url,state,headRefName,mergeable,isDraft`.
  - PR 없으면 → 생성: `gh pr create --fill --base main --head <branch>` (orchestrator가 넘긴 제목/본문 있으면 사용). 생성 후 그 번호로 진행.
  - PR이 이미 merged/closed → 종료 (`status: CONVERGED` 또는 보고).

### Step 1 — 관측 (Observe)
세 신호를 모두 수집한다:

1. **CI/CD 상태**: `gh pr checks <pr>` (pending/pass/fail per check). 실패 체크의 로그: `gh run list --branch <branch> --limit 5` → `gh run view <run-id> --log-failed`.
2. **모든 코멘트** (리뷰 상태 무관, 전부):
   - conversation: `gh pr view <pr> --json comments`
   - inline review 코멘트: `gh api repos/{owner}/{repo}/pulls/<pr>/comments --paginate`
   - review 본문: `gh api repos/{owner}/{repo}/pulls/<pr>/reviews --paginate`
   - `processed_comment_ids`에 없는 것만 *신규*로 취급.
3. **로컬 테스트** (선택, 빠르면): 프로젝트 테스트 러너로 빠른 회귀 확인. CI가 권위이면 생략 가능.

### Step 2 — 진단·분류 (Diagnose & Triage)

각 실패 신호와 신규 코멘트를 분류한다:

| 신호 | 분류 | 행동 |
|------|------|------|
| CI 테스트 실패 | 코드 버그 / flaky | 버그면 수정. flaky 의심이면 재실행 1회 후 판단 |
| CI 빌드/타입/린트 실패 | 객관적 | 자동 수정 |
| 코멘트 — 코드 수정 요청 | actionable | 자동 수정 |
| 코멘트 — 설계/방향/트레이드오프 | 판단 필요 | **에스컬레이션** (사람에게, 코드 자동변경 안 함) |
| 코멘트 — 질문/토론 | 판단 필요 | **에스컬레이션** (답변 초안만 제시) |
| 코멘트 — nit/optional | 저비용 | 적용. 비싸면 노트로 보고 |

> 📌 분류가 애매한 코멘트는 actionable이 아니라 **에스컬레이션**으로 기운다. 잘못 자동수정하면 리뷰어 의도를 어긴다.

### Step 3 — 수정 (Fix)
- 각 actionable 신호에 대해 **해당 스택의 engineer agent**를 디스패치 (sdd-ts-engineer / sdd-rust-engineer / sdd-python-engineer … 범용은 sdd-implementer). 디스패치 prompt에 주입: 실패 로그/코멘트 전문 + 수정 범위 + "이 신호만 해결, 무관한 변경 금지".
- 수정 후 변경을 **head 브랜치에 commit + push**.
- 처리한 코멘트는 `processed_comment_ids`에 추가하고, 가능하면 스레드에 한 줄 답글(`Addressed in <sha>`)을 단다.
- `fix_attempts[signal]` 증가.

### Step 4 — 반복 패턴 감지 + LEARNING append (F15)

이번 패스 종료 전, `fix_attempts` 딕셔너리를 순회해 **동일 신호가 2회 이상** 등록된 패턴을 감지한다.

```
python skills/pr-converge/scripts/pattern_detector.py  # detect_repeated_ci_fail() 호출
```

감지된 패턴마다 `.harness/LEARNING.md`에 provenance-tagged 엔트리를 append한다:

```
python skills/pr-converge/scripts/learning_appender.py  # append_learning_entry() 호출
```

append 엔트리 포맷:
```
## {YYYY-MM-DD} — {signal_key} / pr-converge
<!-- tags: domain=pr-converge, stage=pr-converge, provenance_repo={repo_id} -->

반복 CI/리뷰 실패 패턴: `{signal_key}` — N회 실패.
```

> 📌 `provenance_repo`와 `stage=pr-converge`는 F15 Acceptance 필수 필드. 누락 금지.
> 📌 동일 marker가 이미 LEARNING.md에 있으면 중복 append 하지 않는다 (learning_appender가 자동 skip).

### Step 5 — 기록 + 다음 패스 판정

상태머신으로 종료/계속을 판정하고 `.harness/pr-converge-state.json`을 갱신한다.

상태 전이는 `skills/pr-converge/scripts/state_machine.py`의 `transition_status(state, signals)`를 호출해 결정한다. 직접 산문 로직으로 판단하지 않는다.

```
python skills/pr-converge/scripts/state_machine.py  # transition_status() 호출
```

| status | 조건 | 다음 |
|--------|------|------|
| **CONVERGED** | 모든 CI green + 신규 actionable 코멘트 0 + 미처리 에스컬레이션 0 | 루프 종료. **사람에게 머지 요청.** |
| **WORKING** | 이번 패스에 수정 push함 (CI 재실행 예정) | 다음 틱 ~270s 후 (CI 도는 중, 캐시 warm) |
| **WAITING** | 수정할 것 없고 CI 아직 pending | 다음 틱 ~270s 후 |
| **NEEDS_HUMAN** | 에스컬레이션 코멘트 존재 (설계/토론), 그 외 자동신호는 green | 사람 응답 대기 → 다음 틱 1200s+ (또는 종료하고 사람 호출) |
| **BLOCKED** | 동일 신호 `fix_attempts ≥ 3` 또는 총 `iterations ≥ 15` | 루프 종료. 진단과 함께 에스컬레이션. |

케이던스 계산은 `hooks.lib.self_improve.circuit_breaker.compute_cadence(status)`가 담당한다. 프롬프트에서 직접 케이던스를 하드코딩하지 않는다.

### Step 6 — 보고
매 패스 끝에 보고:
- 현 status + CI 체크 요약(pass/fail/pending) + 이번 패스에 수정한 신호 + 에스컬레이션 목록(있으면 코멘트 원문 링크).
- CONVERGED → "전부 green, 머지 승인 바람". BLOCKED/NEEDS_HUMAN → 무엇이 왜 막혔는지 + 사람이 결정할 항목.

---

## /loop 케이던스 가이드

`/loop` 동적 모드로 재호출될 때 다음 간격 권장 (ScheduleWakeup):

- **WORKING / WAITING** (CI 도는 중): **~270s**. 5분 미만으로 캐시 warm 유지. CI 8분짜리면 270s 두 번이 60s 여덟 번보다 싸다.
- **NEEDS_HUMAN** (사람 코멘트 응답 대기): **1200s+**. 사람이 분 단위로 안 답하니 캐시 미스 감수하고 길게.
- **CONVERGED / BLOCKED**: 루프 종료 (다음 틱 없음).

**300s는 절대 사용하지 않는다.** 캐시 미스 + 분할 이득 없음 — 최악의 케이던스. `compute_cadence()`가 300을 반환하지 않도록 회로 수준에서 보장되어 있다. 270s로 내리거나 1200s+로 올린다.

---

## 서킷브레이커 / 안전

- **동일 신호 3회 수정 실패** → BLOCKED. `check_circuit_breaker(state)`가 결정. 같은 테스트를 무한정 고치려 들지 않는다.
- **총 15 iteration** 초과 → BLOCKED. `check_circuit_breaker(state)`가 결정.
- main 직접 push·force-push 금지. PR head 브랜치만. push 전 브랜치 확인:
  ```bash
  git symbolic-ref --short HEAD  # main/master이면 abort
  git push origin HEAD           # force-push 플래그 절대 금지
  ```
- 자동 수정은 실패 신호가 가리키는 범위로 한정. 무관한 리팩터 금지.
- 에스컬레이션 코멘트는 코드 자동변경 대상이 아니다 — 답변 초안만, 결정은 사람.
- gh 미인증·비-GitHub 원격 → 1패스에서 BLOCKED 보고 후 종료 (조용히 진행 안 함).

> 📌 서킷브레이커 로직은 `hooks.lib.self_improve.circuit_breaker.check_circuit_breaker`에 구현. 프롬프트에서 직접 임계값(3/15)을 하드코딩하지 않는다.

## scripts/ 결정적 글루 참조

판단 로직(gh 관측, 코멘트 분류, 엔지니어 디스패치)은 이 SKILL.md가 담당.  
결정적 로직(임계값 판정, 포맷 직렬화)은 아래 scripts/ 모듈이 담당:

| 모듈 | 함수 | 역할 |
|------|------|------|
| `scripts/state_machine.py` | `transition_status(state, signals)` | 상태 전이 (WORKING/WAITING/NEEDS_HUMAN/CONVERGED/BLOCKED) |
| `scripts/comment_dedup.py` | `filter_new_comments(all_comments, processed_ids)` | 신규 코멘트 필터링 |
| `scripts/pattern_detector.py` | `detect_repeated_ci_fail(fix_attempts, ...)` | 반복 패턴 감지 + LEARNING 페이로드 생성 |
| `scripts/learning_appender.py` | `append_learning_entry(path, entry_dict)` | LEARNING.md provenance-tagged append |

scripts/는 `hooks.lib.self_improve.circuit_breaker`, `hooks.lib.self_improve.parser`를 import해 결정 위임.

## 참조
- 자동 진입: [skills/sdd-orchestrator/SKILL.md — Step 4](../sdd-orchestrator/SKILL.md)
- 수정 디스패치 대상: agents/sdd-*-engineer.md, agents/sdd-implementer.md
- 코어 결정 로직: hooks/lib/self_improve/circuit_breaker.py, hooks/lib/self_improve/parser.py
