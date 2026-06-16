# Self-Improving Harness Spec

## 개요

- **한줄 요약:** PR 수렴 루프(pr-converge)와 자기학습 루프(self-improve)를 결합하여, 하네스가 실제 개발 사이클의 외부 신호와 교훈을 흡수해 스스로 개선되는 자가개선 시스템
- **타겟 사용자:** moon-harness 플러그인을 사용해 AI 에이전트 기반 개발을 수행하는 개발자
- **핵심 가치:** "루프를 돌았다" ≠ "실제로 개선됐다" — 측정 가능한 fitness function으로만 개선을 인정하고, 범용 플러그인이 단일 프로젝트 편향으로 퇴화하지 않도록 2티어 위험도 격리와 교차 프로젝트 기준을 강제한다

---

## 플랫폼 / 스택 (SIMPLE 모드 판정)

| 항목 | 값 |
|------|----|
| 모드 | **SIMPLE** — UI 없음, REST API 계약 없음 |
| SIMPLE 판정 근거 | 내부 툴링(스크립트·마크다운 SKILL/agent·hooks·pytest/eval)만 존재. 외부 사용자 인터페이스 또는 API 엔드포인트 없음 |
| 언어/런타임 | Python 3 (stdlib only), bash |
| 테스트 | pytest (결정적 로직), claude -p 헤드리스 (LLM 판단 로직) |
| 외부 의존 | gh CLI (GitHub 전제), Claude Code (skills/agents/hooks 마크다운) |
| 상태 파일 | JSON (커서·서킷브레이커), 마크다운 (append-only 로그·제안 큐) |
| 선례 | stop-pipeline.py, pr-converge-state.json, retro-state.json |

---

## 사용자 요구사항 원문 → 기능 매핑

| # | 사용자 요구 원문 | 기능 |
|---|----------------|------|
| R1.1 | "PR을 던지고 끝내지 않고 CI/CD·테스트·빌드·린트·리뷰 코멘트가 전부 green이 될 때까지 수렴" | F1, F4 |
| R1.2 | "모든 코멘트 확인 — 공식 'Request changes' 리뷰 상태에 의존 안 함. conversation + inline review + review 본문 전부 수집, 하나도 무시 안 함" | F2 |
| R1.3 | "객관 신호(CI/테스트/빌드/린트)는 자동 수정·push. 코멘트는 코드수정 요청만 자동, 설계/토론/질문은 에스컬레이션. 애매하면 에스컬레이션" | F3 |
| R1.4 | "/loop로 주기 실행(1 호출 = 1 관측→수정 패스). 케이던스: CI 도는 중 ~270s, 사람 대기 1200s+, 300s 회피" | F4 |
| R1.5 | "최종 머지는 사람 승인. main 직접 push·force-push 금지, head 브랜치만" | F5 |
| R1.6 | "서킷브레이커: 동일 신호 3회 / 총 15회 → BLOCKED + 에스컬레이션" | F6 |
| R1.7 | "통합: sdd-orchestrator의 main 직접머지를 PR 기반 흐름+수렴 루프로 교체. 독립 스킬 /pr-converge로 SDD 밖에서도 사용" | F1, F7 |
| R2.1 | ".harness/LEARNING.md raw 신호 → 진단·검증·반영 자동화(수동 승격 대체)" | F8, F9, F10 |
| R2.2 | "2티어: 프로젝트 티어=검증 후 자동 / 하네스 티어=제안만+사람승인. 애매하면 하네스 티어" | F11 |
| R2.3 | "검증 게이트: harness-improvement-critic 반박(UPHELD/REFUTED/NARROW) + 정합성 + anti-overfit" | F12 |
| R2.4 | "롤백 가능 기록, 프로젝트 티어 자동적용 5건 상한" | F13 |
| R2.5 | "트리거: 실제 머지 이벤트 기반(pr-converge가 CONVERGED+머지 시 호출) + /self-improve 수동" | F14 |
| R2.5(연결) | "pr-converge가 배운 교훈(반복 CI 실패·리뷰 패턴)을 LEARNING.md에 append → self-improve 입력" | F15 |
| R2.6 | "오염 격리: (a)각 엔트리 provenance (b)하네스 티어 승격=서로 다른 프로젝트 2곳+ 재현 (c)기본값 프로젝트 티어 (d)critic 무해성+롤백로그=회귀 방어" | F16 |
| R2.7 | "학습 메커니즘 사다리 + 재발 기반 에스컬레이션: L0~절차적 메모리. @LEARNING.md 통째 import 폐기→태그 on-demand 로드" | F17, F18 |
| R2.8 | "자동 스킬 생성/진화: 성공/교정 절차를 스킬로 결정화. 티어링. protected set. 벤치 게이밍 감시. 다윈식 prune" | F19 |
| R3.1 | "결정적 로직은 Python stdlib + pytest. 결정/판단 분리" | F20 |
| R3.2 | "eval 2계층: 오프라인(골든 라벨, assertion, 비용0, CI) + 라이브(claude -p 헤드리스 + LLM-judge)" | F21 |
| R3.3 | "벤치=fitness function: 개선안 → 벤치 OFF=baseline vs ON → 점수↑ AND held-out 회귀0 → 채택" | F22 |
| R3.4 | "지표: 객관(앵커)=수렴성공률·green까지 iteration·재발률·오에스컬레이션률; 판단(보조)=코멘트분류정확도 등" | F23 |
| R3.5 | "벤치 규율: frozen·버전관리, held-out 분할(Goodhart 방지), frozen baseline 하네스+사람골든 대비, 콜드스타트 인정" | F24 |
| R3.6 | "핵심 성공지표='같은 교훈이 더는 안 쌓인다'(재발률 감소)" | F23 |
| 메모리 | "2계층(작은 고정 always-on + 큰 검색형 on-demand)+토큰예산(~800/~500)을 기존 메모리+스킬 인덱스에 매핑. 유일 신규=LEARNING.md 통째 import 폐기→on-demand 검색/태그 로드. 3-스코프(유저/repo/플러그인) 분리" | F18 |
| phase | "Phase1(안전즉효) → Phase2(측정 substrate) → Phase3(고급위험). 측정기반 생기기 전엔 위험부분 안 만듦" | NFR-3 |
| prior art | "초안 이미 존재: skills/self-improve/SKILL.md, skills/pr-converge/SKILL.md, agents/harness-improvement-critic.md, sdd-orchestrator Step4/5. 이 초안을 spec과 정합하게 재검토 대상으로 명시" | NFR-4 |

---

## 기능 요구사항

### F1: PR 기반 수렴 루프 진입점 (pr-converge 스킬)

WHEN `/pr-converge` 또는 `/pr-converge <pr-number>`가 호출될 때 THE SYSTEM SHALL 현재 브랜치(또는 지정 PR)를 대상으로 1패스(관측→수정)를 실행하고, 패스 종료 시 현재 status와 다음 권장 간격을 보고한다.

WHEN `sdd-orchestrator` Step 4가 완료될 때 THE SYSTEM SHALL pr-converge를 호출하여 PR 기반 수렴 루프를 시작한다(main 직접 머지 대체).

WHERE `/pr-converge`가 SDD 컨텍스트 밖에서 호출될 때 THE SYSTEM SHALL sdd-orchestrator 없이 독립적으로 동작한다.

- **Acceptance:** `/pr-converge`가 SDD 없이 임의 브랜치에서 호출되어도 1패스 완료 보고가 나온다. sdd-orchestrator Step 4 호출 시 main 직접 머지가 일어나지 않는다.

---

### F2: 전체 코멘트 수집 (리뷰 상태 무관)

WHEN 1패스의 관측 단계가 실행될 때 THE SYSTEM SHALL `gh pr view --json comments`, `gh api pulls/<pr>/comments --paginate`, `gh api pulls/<pr>/reviews --paginate`를 통해 conversation·inline review·review 본문을 전부 수집하고, 공식 "Request changes" 리뷰 상태의 존재 여부와 무관하게 모든 코멘트를 처리 대상에 포함한다.

THE SYSTEM SHALL `.harness/pr-converge-state.json`의 `processed_comment_ids`를 대조해 신규 코멘트만 미처리로 분류하며, 이전에 처리한 코멘트를 재처리하지 않는다.

IF 수집 API 호출이 실패할 때 THEN THE SYSTEM SHALL 해당 오류를 보고하고 status를 BLOCKED로 설정한 뒤 패스를 종료한다.

- **Acceptance:** PR에 "Request changes" 리뷰 상태 없이 conversation 코멘트만 있는 시나리오에서 해당 코멘트가 미처리 목록에 포함된다. 한 코멘트가 두 패스에서 중복 처리되지 않는다.

---

### F3: 신호 분류 및 에스컬레이션 판정

WHEN 신호(CI 실패 또는 신규 코멘트)가 수집될 때 THE SYSTEM SHALL 각 신호를 다음 기준으로 분류한다:
- CI/빌드/타입/린트 실패 → actionable(자동 수정 대상)
- 코멘트: 명시적 코드 수정 요청 → actionable
- 코멘트: 설계·방향·트레이드오프·질문·토론 → escalation
- 코멘트: nit/optional → actionable(저비용) 또는 보고

WHEN 코멘트 분류가 actionable인지 escalation인지 불명확할 때 THE SYSTEM SHALL escalation으로 분류한다(보수적 기본값).

WHEN actionable 신호가 존재할 때 THE SYSTEM SHALL 해당 스택의 engineer agent(sdd-ts-engineer, sdd-rust-engineer, sdd-python-engineer 등, 범용은 sdd-implementer)를 디스패치하고, 디스패치 프롬프트에 실패 로그/코멘트 전문·수정 범위·"이 신호만 해결, 무관한 변경 금지" 지침을 포함한다.

WHEN escalation 신호가 존재할 때 THE SYSTEM SHALL 해당 코멘트 원문과 링크를 사용자에게 전달하고, 코드 자동 변경을 수행하지 않는다.

- **Acceptance:** 설계 토론 코멘트를 포함한 PR에서 해당 코멘트에 대한 코드 수정 commit이 생성되지 않는다. CI 실패는 engineer agent 디스패치 후 commit이 생성된다.

---

### F4: /loop 1패스 구조 및 케이던스

THE SYSTEM SHALL `/loop /pr-converge` 조합에서 1회 호출 = 1 관측→수정 패스를 실행하고, 패스 완료 시 다음 틱 간격을 다음 규칙으로 결정하여 보고한다:
- status가 WORKING 또는 WAITING일 때: ~270s
- status가 NEEDS_HUMAN일 때: 1200s 이상
- status가 CONVERGED 또는 BLOCKED일 때: 루프 종료(다음 틱 없음)

THE SYSTEM SHALL 300s 간격을 권장 간격으로 사용하지 않는다(캐시 미스 + 분할 이득 없음).

- **Acceptance:** WORKING 상태 보고에 270s 간격이 명시된다. CONVERGED 상태에서 루프 재호출이 없다.

---

### F5: main 보호 및 안전한 push

THE SYSTEM SHALL PR head 브랜치에만 commit 및 push를 수행한다.

THE SYSTEM SHALL main(또는 기본 브랜치)에 대한 직접 push 및 force-push를 수행하지 않는다.

WHEN 원격 head 브랜치가 로컬보다 앞서 있을 때 THE SYSTEM SHALL rebase 또는 pull 후 push를 진행한다.

WHEN PR이 존재하지 않을 때 THE SYSTEM SHALL `gh pr create --fill --base main --head <branch>`로 PR을 생성한 뒤 수렴을 시작한다.

- **Acceptance:** 수렴 루프가 실행된 후 main 브랜치의 commit 이력에 루프가 생성한 commit이 나타나지 않는다. force-push 명령이 실행되지 않는다.

---

### F6: 서킷브레이커

WHEN 동일 신호에 대한 `fix_attempts`가 3 이상일 때 THE SYSTEM SHALL status를 BLOCKED로 설정하고 진단 내용과 함께 사용자에게 에스컬레이션하며 루프를 종료한다.

WHEN `iterations`가 15를 초과할 때 THE SYSTEM SHALL status를 BLOCKED로 설정하고 사용자에게 에스컬레이션하며 루프를 종료한다.

WHEN `gh auth status`가 실패할 때 THE SYSTEM SHALL 첫 패스에서 BLOCKED를 보고하고 조용히 진행하지 않는다.

- **Acceptance:** 동일 CI 실패를 3회 수정 시도 후 BLOCKED 보고가 나오고 4번째 수정 시도가 없다. 총 16회 패스에서 BLOCKED가 발생한다.

---

### F7: sdd-orchestrator 통합

WHEN sdd-orchestrator Step 4 완료 처리가 실행될 때 THE SYSTEM SHALL main 직접 머지 대신 `Skill(pr-converge)`를 호출하여 PR을 열고 수렴 루프를 시작한다.

WHEN pr-converge가 CONVERGED를 보고할 때 THE SYSTEM SHALL 사용자에게 결과와 머지 승인 요청을 전달한다.

WHEN pr-converge가 NEEDS_HUMAN 또는 BLOCKED를 보고할 때 THE SYSTEM SHALL 막힌 항목(설계 코멘트·반복 실패)을 사용자에게 에스컬레이션한다.

- **Acceptance:** sdd-orchestrator Step 4 실행 후 main에 직접 commit이 없고 PR이 생성되어 있다.

---

### F8: LEARNING.md 신규 엔트리 수집 (커서 기반)

WHEN self-improve가 실행될 때 THE SYSTEM SHALL `.harness/retro-state.json`의 `last_processed_marker`를 읽어, 그 마커 이후의 `##` 엔트리만 신규로 취급한다.

WHEN `retro-state.json`이 없을 때 THE SYSTEM SHALL LEARNING.md 전체를 신규로 취급한다.

WHEN 신규 엔트리가 0건일 때 THE SYSTEM SHALL "신규 교훈 없음"을 보고하고 커서를 갱신하지 않으며 종료한다.

WHEN LEARNING.md가 없거나 헤더만 있을 때 THE SYSTEM SHALL "신호 없음"을 보고하고 종료한다.

THE SYSTEM SHALL LEARNING.md 원본을 수정하거나 삭제하지 않는다(읽기 전용 입력).

- **Acceptance:** 이미 처리된 엔트리를 포함하는 LEARNING.md에서 두 번째 실행 시 신규 엔트리만 진단 대상이 된다.

---

### F9: 진단 및 클러스터링

WHEN 신규 엔트리가 존재할 때 THE SYSTEM SHALL 엔트리를 주제·대상별로 클러스터링하고, 각 클러스터에 대해 다음 기준으로 개선 후보 여부를 판정한다:
- 독립 신호 2건 이상 또는 한 엔트리에 명시적 반복 신호("또 그러네" 등) → 개선 후보
- 1회성·맥락 한정 → 개선 후보 아님(docs/lessons-learned.md에 참고 노트로만)

WHEN 개선 후보가 도출될 때 THE SYSTEM SHALL 대상 아티팩트를 특정하고, 추가/수정할 정확한 텍스트(또는 diff)와 위치(파일:섹션)를 포함하는 구체적 변경안을 작성한다. 추상적 조언("더 신중히 하라" 류)은 변경안으로 인정하지 않는다.

- **Acceptance:** 동일 패턴이 1건만 있는 엔트리가 행동 규칙 변경 후보로 등록되지 않는다. 변경안에 대상 파일 경로와 구체적 텍스트가 포함된다.

---

### F10: 검증 게이트 (정합성 사전검사)

WHEN 개선 후보가 존재할 때 THE SYSTEM SHALL 반박 agent 호출 전에 다음 결정적 사전검사를 순서대로 수행한다:
- 충돌 검사: 대상 파일에 모순되는 규칙이 존재하는지 확인
- 중복 검사: 동일 취지가 이미 기록되어 있으면 후보를 폐기(사유: 중복)
- 일반성 검사: 신호 2건 미만이고 반복 신호 없으면 행동 규칙 변경에서 강등

- **Acceptance:** 대상 파일에 이미 동일 내용이 존재하는 후보에 대해 반박 agent가 호출되지 않고 "중복"으로 폐기된다.

---

### F11: 2티어 분류 및 자율성 통제

WHEN 개선 후보의 티어를 분류할 때 THE SYSTEM SHALL 다음 기준을 적용한다:
- 변경이 현재 repo 안에서만 의미를 가지면 → 프로젝트 티어(자동 적용 대상)
- 변경이 agent·skill·hook의 일반 동작을 바꾸면 → 하네스 티어(제안만)
- 분류가 불명확하면 → 하네스 티어(보수적 기본값)

WHEN 개선 후보가 프로젝트 티어이고 검증 게이트를 통과할 때 THE SYSTEM SHALL 대상 파일(docs/lessons-learned.md, docs/pitfalls.md, .harness/* 설정)에 변경을 직접 적용한다.

WHEN 개선 후보가 하네스 티어이고 검증 게이트를 통과할 때 THE SYSTEM SHALL `.harness/harness-proposals/{YYYY-MM-DD}-{slug}.md`를 생성하고(대상 파일 경로, 정확한 diff, 근거 엔트리, critic 판정 포함), 플러그인 파일은 편집하지 않으며, 사용자에게 경로를 보고한다.

THE SYSTEM SHALL 하네스 티어 변경을 회수와 무관하게 자동 적용하지 않는다.

THE SYSTEM SHALL 프로젝트 티어라도 사용자 CLAUDE.md 본문을 직접 편집하지 않는다.

- **Acceptance:** 하네스 티어로 분류된 개선안이 UPHELD 판정을 받아도 플러그인 파일에 편집이 발생하지 않는다. harness-proposals/ 아래 파일이 생성된다.

---

### F12: harness-improvement-critic 반박 검증

WHEN 정합성 사전검사를 통과한 개선 후보가 있을 때 THE SYSTEM SHALL `harness-improvement-critic` agent를 호출하고, 다음 입력을 프롬프트에 주입한다: 개선안(대상 파일:섹션 + diff) + 근거 엔트리 전문 + 대상 파일 현재 내용 + 사전검사 결과.

THE SYSTEM SHALL critic 판정에 따라 다음과 같이 처리한다:
- UPHELD → 적용 또는 제안 진행
- NARROW → critic이 제시한 좁힌 버전으로 진행
- REFUTED → 폐기(사유 기록)

WHEN critic 판정이 REFUTED일 때 THE SYSTEM SHALL 실패 기준과 사유를 retro-log.md에 기록한다.

- **Acceptance:** REFUTED 판정을 받은 후보가 프로젝트 티어 파일에 적용되지 않는다. NARROW 판정 시 원본 안이 아닌 좁힌 버전이 적용된다.

---

### F13: 롤백 가능 기록 및 자동 적용 상한

WHEN 프로젝트 티어 변경이 자동 적용될 때 THE SYSTEM SHALL `.harness/retro-log.md`에 before/after diff를 포함하는 롤백 블록을 기록한다.

WHEN 한 회고 실행에서 프로젝트 티어 자동 적용 후보가 5건을 초과할 때 THE SYSTEM SHALL 5건만 적용하고 초과분을 하네스 제안 큐 또는 다음 회고로 미루며, 잘라낸 사실을 보고에 명시한다(silent truncation 금지).

WHEN 회고 실행 중 오류가 발생할 때 THE SYSTEM SHALL 커서를 갱신하지 않고 중단하여 다음 실행이 같은 엔트리를 다시 처리하도록 한다. 부분 적용분은 retro-log에 기록하여 롤백 가능하게 한다.

- **Acceptance:** retro-log.md에 롤백 블록이 없는 자동 적용이 존재하지 않는다. 6건 이상의 후보가 있는 회고에서 적용 건수가 5건 이하이고 초과 건수가 보고에 명시된다.

---

### F14: self-improve 트리거

WHEN pr-converge가 CONVERGED를 보고하고 사용자가 머지를 승인한 후 THE SYSTEM SHALL `.harness/LEARNING.md`에 이번 사이클 신규 엔트리가 존재하는지 확인하고, 존재하면 `Skill(self-improve)`를 호출한다.

WHEN `/self-improve`가 수동으로 호출될 때 THE SYSTEM SHALL 자동 트리거와 동일한 루프를 실행한다.

WHEN self-improve가 실패하거나 건너뛸 때 THE SYSTEM SHALL 사이클 완료 상태에 영향을 주지 않는다.

- **Acceptance:** sdd-orchestrator가 머지 승인 후 자동으로 self-improve를 호출한다. self-improve 실패 시 사이클 완료 보고가 차단되지 않는다.

---

### F15: pr-converge → LEARNING.md 교훈 기록

WHEN pr-converge 수렴 루프에서 반복 CI 실패 패턴(동일 신호 2회 이상)이 감지될 때 THE SYSTEM SHALL 해당 패턴을 `.harness/LEARNING.md`에 append한다. 엔트리에는 provenance(출처 repo, 발견 단계: pr-converge)가 포함된다.

WHEN pr-converge 수렴 루프에서 반복 리뷰 코멘트 패턴이 감지될 때 THE SYSTEM SHALL 해당 패턴을 `.harness/LEARNING.md`에 append한다.

- **Acceptance:** 동일 CI 체크가 2회 실패한 후 LEARNING.md에 해당 패턴 엔트리가 생성된다. 엔트리에 `source_repo`, `discovered_at: pr-converge` 필드가 존재한다.

---

### F16: 오염 격리 (provenance + 교차 프로젝트 기준)

THE SYSTEM SHALL LEARNING.md의 각 엔트리에 다음 provenance를 포함한다: 출처 repo 식별자, 발견 단계(구현/pr-converge).

WHEN 하네스 티어 개선 후보를 평가할 때 THE SYSTEM SHALL 단일 프로젝트 내 반복(동일 repo N건)과 교차 프로젝트 재현(서로 다른 repo 2곳 이상)을 구분하고, 교차 프로젝트 재현이 없으면 하네스 티어 승격 후보가 아닌 프로젝트 티어로 분류한다.

WHEN harness-improvement-critic이 개선안을 평가할 때 THE SYSTEM SHALL 하네스 티어 후보에 대해 "모든 프로젝트에 적용된다"는 전제 하에 무해성 기준을 더 엄격하게 적용한다.

- **Acceptance:** 단일 repo에서 5회 반복된 패턴이 하네스 티어로 자동 승격되지 않는다. 하네스 티어 제안 파일에 교차 프로젝트 근거가 명시되지 않은 경우 REFUTED 또는 NARROW로 판정된다.

---

### F17: 학습 메커니즘 사다리 (L0–L4 + 절차적 메모리)

THE SYSTEM SHALL 교훈을 다음 사다리 순서로 적용하고, 재발 횟수에 따라 한 단계씩 에스컬레이션한다:
- L0: passive — LEARNING.md에 기록(입력층)
- L1: 큐레이션/압축 — docs/lessons-learned.md에 일반화 교훈 기록
- L2: 관련성 라우팅 — 태그 on-demand 로드(progressive disclosure)
- L3: enforcement — 교훈을 hooks/체크로 구현
- L4: 프롬프트/agent 수정 — 사람 게이트 필수
- 절차적 메모리: 성공 절차의 스킬 결정화

WHEN 동일 교훈이 재발할 때 THE SYSTEM SHALL 현재 사다리 단계보다 한 단계 높은 메커니즘을 제안한다.

- **Acceptance:** L1에 기록된 교훈이 재발하면 L2(on-demand 라우팅) 적용이 제안된다. L3 이상의 적용은 사람 승인 없이 자동 실행되지 않는다(L3 hook 생성은 하네스 티어에 해당하므로 F11 적용).

---

### F18: LEARNING.md on-demand 로드 (통째 @import 폐기)

THE SYSTEM SHALL CLAUDE.md 또는 skill 프롬프트에서 `@.harness/LEARNING.md` 전체를 항상 로드하는 방식을 사용하지 않는다.

THE SYSTEM SHALL LEARNING.md 엔트리에 태그(도메인, 단계, provenance)를 부여하고, 관련 작업 컨텍스트에서 해당 태그로 필터링된 엔트리만 on-demand로 로드한다.

THE SYSTEM SHALL 항상 로드되는 always-on 계층의 토큰 예산을 ~800 토큰 이내로 유지하고, on-demand 검색형 계층은 ~500 토큰 이내로 유지한다.

THE SYSTEM SHALL 유저/repo/플러그인 3개 스코프의 메모리를 분리하여 관리하며, 플러그인 스코프 메모리를 유저 또는 repo 스코프에 혼합하지 않는다.

- **Acceptance:** 새 SDD 사이클 시작 시 LEARNING.md 전체 내용이 컨텍스트에 자동 포함되지 않는다. 관련 태그의 엔트리만 로드됨을 로그로 확인할 수 있다.

---

### F19: 자동 스킬 생성/진화 (결정화)

WHEN 다음 조건 중 하나가 충족될 때 THE SYSTEM SHALL 해당 절차를 스킬로 결정화하는 제안을 생성한다:
- 동일 tool 사용 성공 패턴이 5회 이상 기록됨
- 오류-막다른길 후 작동 경로가 발견됨
- 사용자 교정이 기록됨

WHEN 스킬 결정화 대상이 프로젝트 티어일 때 THE SYSTEM SHALL 해당 스킬을 자동 생성한다(사람 게이트 없음).

WHEN 스킬 결정화 대상이 하네스 티어일 때 THE SYSTEM SHALL 스킬 초안과 교차 프로젝트 재현 근거 및 벤치마크 델타를 포함한 제안을 생성하고, 사람 승인 없이 플러그인 파일에 기록하지 않는다.

THE SYSTEM SHALL 다음 protected set의 스킬·agent를 자동 생성 또는 자동 수정의 대상으로 삼지 않는다: self-improve, pr-converge, harness-improvement-critic, 게이트 로직 스크립트.

WHEN 동일 목적의 스킬이 이미 존재할 때 THE SYSTEM SHALL 중복 생성 대신 기존 스킬과의 dedup/merge를 제안한다.

THE SYSTEM SHALL 스킬 총 목록이 상한을 초과할 때 저재사용 스킬을 아카이브 대상으로 식별하고 사용자에게 제안한다.

WHEN 벤치마크 점수가 스킬 변경 후 held-out 셋에서 이전 대비 하락할 때 THE SYSTEM SHALL 해당 스킬 변경을 채택하지 않는다(벤치 게이밍 방어).

- **Acceptance:** protected set에 포함된 pr-converge/SKILL.md가 자동 생성 루프에 의해 수정되지 않는다. 스킬 description이 기존 스킬과 충돌할 경우 충돌 경고가 생성된다.

---

### F20: 결정적 로직의 Python 구현

THE SYSTEM SHALL 상태머신 전이, 서킷브레이커 게이트, 커서 갱신, 케이던스 계산, 상한 적용 등 결정적 로직을 Python stdlib 스크립트(pytest 검증 가능)로 구현한다.

THE SYSTEM SHALL LLM 판단이 필요한 로직(코멘트 분류, 클러스터링, critic 반박)만 프롬프트(마크다운 skill/agent)로 구현한다.

THE SYSTEM SHALL 결정적 로직 스크립트에서 외부 네트워크 호출 또는 LLM API 호출을 수행하지 않는다.

- **Acceptance:** 상태 전이 로직이 pytest로 실행 가능하고 네트워크 없이 통과한다. `stop-pipeline.py` 선례와 동일한 패턴을 따른다.

---

### F21: eval 2계층 구현

THE SYSTEM SHALL 결정적 로직에 대한 오프라인 eval을 pytest + 골든 라벨 fixture로 구현하고, CI에서 자동 실행한다(비용 0, 네트워크 의존 없음).

WHEN 라이브 eval이 필요할 때 THE SYSTEM SHALL `claude -p` 헤드리스 실행 + LLM-judge 방식으로 구현하고, 오프라인 eval과 별도 단계로 분리한다.

THE SYSTEM SHALL 오프라인 eval과 라이브 eval을 동일 파이프라인 단계에서 혼합하지 않는다.

- **Acceptance:** `pytest tests/` 명령이 gh CLI, claude API 없이 완료된다. 라이브 eval 실행 시 별도 플래그 또는 단계로 구분된다.

---

### F22: 벤치마크 fitness function

WHEN 하네스 티어 개선안(스킬·agent·hook 변경 포함)이 채택 여부를 결정할 때 THE SYSTEM SHALL 다음 절차를 거친다:
1. baseline 측정: 개선안 OFF 상태의 벤치마크 점수 기록
2. 개선안 ON 상태의 벤치마크 점수 측정
3. 점수가 상승하고 held-out 셋에서 회귀가 없을 때에만 채택

THE SYSTEM SHALL critic(harness-improvement-critic) 주관 판정을 벤치마크 점수 델타의 보조 수단으로 사용하며, 점수 델타가 측정 가능한 경우 객관 점수가 우선한다.

- **Acceptance:** 벤치마크 점수가 하락하는 개선안이 UPHELD critic 판정에도 불구하고 채택되지 않는다.

---

### F23: 핵심 지표 측정

THE SYSTEM SHALL 다음 **자동 측정 가능** 지표(Phase 2 구현)를 측정하고 기록한다:
- pr-converge 수렴 성공률 (CONVERGED / 전체 실행)
- green까지 평균 iteration 횟수
- 동일 교훈 재발률 (핵심 앵커)
- 코멘트 분류 정확도 (actionable/escalation 분류의 사후 정확도)
- 스킬 reuse rate 및 success rate

THE SYSTEM SHALL 다음 **사후 사람 검토** 지표(Phase 2.5 / Phase 3 초입, 초기 데이터 누적 후)를 측정하고 기록한다:
- 오에스컬레이션률 (escalation이 불필요했던 신호의 에스컬레이션 비율 — 사후 검토로만 측정 가능)
- critic UPHELD/REFUTED/NARROW precision·recall (초기 라벨 누적 필요)

> blocker-check Issue 3 반영: 자동 측정 불가 지표(오에스컬레이션률·critic precision/recall)를 Phase 2 핵심 fitness function에서 분리해, Phase 2는 자동 측정만으로 완성되도록 한다.

THE SYSTEM SHALL 핵심 성공 기준으로 "동일 교훈이 더는 LEARNING.md에 쌓이지 않는다(재발률 감소)"를 사용한다.

- **Acceptance:** 재발률이 `.harness/retro-log.md` 또는 별도 지표 파일에서 추적 가능하다. 재발률 측정이 사람이 수동으로 집계하지 않아도 가능한 형태로 기록된다.

---

### F24: 벤치마크 규율 (frozen · held-out · 콜드스타트)

THE SYSTEM SHALL 벤치마크 셋을 버전 관리하고, 평가 실행 중 벤치마크 셋을 수정하지 않는다(frozen).

THE SYSTEM SHALL 벤치마크 셋을 훈련용과 held-out으로 분리하고, 개선안 최적화에 held-out 셋을 사용하지 않는다(Goodhart 방지).

THE SYSTEM SHALL 측정 데이터가 충분하지 않은 초기(콜드스타트) 상태를 인정하고, 데이터 부족 시 측정 불가 상태를 명시하며 추정 기반 채택을 수행하지 않는다.

- **Acceptance:** held-out 셋 파일이 개선안 평가 루프에서 직접 수정되지 않는다. 데이터 5건 미만 시 "콜드스타트, 측정 불가"로 보고된다.

---

## 상태 파일 계약 (State File Schema)

### `.harness/pr-converge-state.json`

```json
{
  "schema_version": 1,
  "pr": "<number>",
  "branch": "<branch-name>",
  "processed_comment_ids": ["<id>"],
  "fix_attempts": { "<signal-key>": "<count>" },
  "iterations": "<number>",
  "status": "WORKING | WAITING | NEEDS_HUMAN | CONVERGED | BLOCKED",
  "last_tick_at": "<ISO8601>",
  "escalations": ["<comment-url>"],
  "learning_entries_appended": ["<marker>"]
}
```

### `.harness/retro-state.json`

```json
{
  "schema_version": 1,
  "last_processed_marker": "<## YYYY-MM-DD — feature / T-XX>",
  "last_retro_at": "<ISO8601>",
  "cumulative": {
    "applied_project": "<number>",
    "proposed_harness": "<number>",
    "dropped": "<number>"
  }
}
```

### `.harness/retro-log.md` (append-only)

```
## {YYYY-MM-DD} retro — 신규 {N}건 처리 / 적용 {A} · 제안 {P} · 폐기 {D}

### 적용 (프로젝트 티어, 자동)
- **{대상파일}** ← {교훈 한 줄}
  - critic: UPHELD | NARROW
  - 근거: {LEARNING 엔트리 마커들}
  - rollback:
    ```diff
    + 추가된 텍스트
    ```

### 제안 (하네스 티어, 승인 대기)
- `harness-proposals/{date}-{slug}.md` — {한 줄 요약}

### 폐기
- {교훈} — REFUTED: {사유} | 1회성 | 중복
```

---

## 비기능 요구사항

### NFR-1: 결정적/판단 로직 분리

결정적 로직(상태 전이, 게이트, 커서, 케이던스, 상한)은 Python stdlib 스크립트로 구현하고 pytest로 검증 가능해야 한다. LLM API 없이 테스트가 통과해야 한다.

### NFR-2: 오염 격리 불변식

하네스 티어 변경에 대해 다음 조건이 항상 성립해야 한다:
- 교차 프로젝트 2곳 이상 재현 근거 없이 하네스 티어 자동 승격 없음
- protected set(self-improve, pr-converge, harness-improvement-critic, 게이트 스크립트) 자동 수정 없음
- 사람 승인 없이 플러그인 파일 편집 없음

### NFR-3: 단계적 phase 로드맵

- **Phase 1 (안전즉효):** 프로젝트 티어 스킬 결정화 + progressive disclosure(F17, F18, F19 프로젝트 티어 범위)
- **Phase 2 (측정 substrate):** 벤치마크 인프라 + reuse/success 지표 + provenance 추적(F20, F21, F22, F23, F24)
- **Phase 3 (고급위험):** Phase 2 측정 기반 확보 후에만 시작. 하네스 티어 자동 승격 제안(F19 하네스 티어, F22 확장). 측정 기반 없이 Phase 3 항목을 구현하지 않는다.

### NFR-4: Prior Art 정합성 검토 (Phase 2 설계의 명시적 task)

다음 기존 초안 산출물을 이 spec과 **라인 단위로 대조**하여 불일치를 해소한 후 구현한다. 이는 Phase 2(설계) 진입 시 별도 task로 수행하며, 검토 시점/담당이 불명확하지 않도록 체크리스트로 고정한다 (blocker-check Issue 2 반영):

- [ ] `skills/self-improve/SKILL.md` — R2.5/F14 트리거(orchestrator 선형배선 → 머지 이벤트 기반) 정합. 추가로 R2.6~R2.8(오염격리·학습사다리·스킬결정화)은 초안에 **미반영**이므로 신규 설계 대상.
- [ ] `skills/pr-converge/SKILL.md` — R1.4 케이던스(300s 회피), R1.7 독립 스킬 동작, F15(LEARNING.md append) 정합. F15는 초안에 **미반영**.
- [ ] `agents/harness-improvement-critic.md` — F22 벤치마크 게이트 격상(critic 주관 → 객관 점수 보조)과 critic 역할 재정의 정합. F16 교차프로젝트 무해성 기준 **미반영**.
- [ ] `skills/sdd-orchestrator/SKILL.md` Step 4/5 — F7(main 직접 머지 → PR 기반) 이미 반영됨. F14(머지 이벤트 기반 self-improve 트리거) 정합 확인.
- [ ] 신규 결정적 스크립트(F20)는 초안에 **없음** — Phase 2에서 전면 신설.

---

## 용어 정의

| 용어 | 정의 |
|------|------|
| pr-converge | PR을 CI/CD·테스트·빌드·린트·모든 리뷰 코멘트에 대해 green이 될 때까지 자동 수렴시키는 스킬 |
| self-improve | LEARNING.md의 raw 교훈을 진단·검증·반영하는 자가개선 회고 루프 스킬 |
| 프로젝트 티어 | 현재 repo 안에만 영향을 미치는 변경. docs/lessons-learned.md, docs/pitfalls.md, .harness/* (설정/로그 외). 검증 후 자동 적용 가능 |
| 하네스 티어 | 설치된 모든 프로젝트에 전파되는 플러그인 변경. skills/**/SKILL.md, agents/*.md, hooks/**. 제안만, 사람 승인 필수 |
| protected set | self-improve, pr-converge, harness-improvement-critic, 게이트 로직 스크립트. 자동 생성/수정 금지 |
| LEARNING.md | .harness/ 아래의 raw append-only 교훈 로그. self-improve의 입력 전용, 수정 불가 |
| fitness function | "루프가 들어갔다 ≠ 실제 개선"을 방지하기 위한 객관 벤치마크 점수. 개선 채택의 주 판단 근거 |
| held-out | 개선안 최적화에 사용하지 않는 frozen 벤치마크 분할. Goodhart 법칙 방어 |
| CONVERGED | pr-converge의 종료 상태: 모든 CI green + 신규 actionable 코멘트 0 + 미처리 에스컬레이션 0 |
| BLOCKED | pr-converge 또는 self-improve의 오류 종료 상태. 사람 에스컬레이션 필요 |
| provenance | 각 LEARNING.md 엔트리의 출처 정보: 출처 repo 식별자 + 발견 단계(구현/pr-converge) |
| 교차 프로젝트 재현 | 서로 다른 repo 2곳 이상에서 동일 패턴이 관찰됨. 하네스 티어 승격의 필요 조건 |
| 결정화 (crystallization) | 반복 성공 절차를 재사용 가능한 스킬로 변환하는 행위 |
| anti-overfit | 독립 신호 2건 미만의 1회성 교훈으로 행동 규칙을 변경하지 않는 원칙 |
| 서킷브레이커 | 동일 신호 3회 또는 총 15 iteration 초과 시 루프를 BLOCKED로 전환하는 안전장치 |
| on-demand 로드 | LEARNING.md 전체를 항상 컨텍스트에 포함하는 대신, 관련 태그의 엔트리만 필요 시 로드하는 방식 |

---

## 미해결 / 가정

### 해결 1: LEARNING.md 태그 포맷 (blocker-check에서 결정)

R2.7/F18의 "태그 on-demand 로드"를 위해 LEARNING.md 엔트리 헤더 직후에 마크다운 메타블록 형식의 태그를 둔다:

```markdown
## {YYYY-MM-DD} — {feature-slug} / {task-id}
<!-- tags: domain={영역}, stage={구현|pr-converge}, provenance_repo={repo-id} -->
```

on-demand 로더는 이 메타블록을 파싱해 현재 작업 컨텍스트의 도메인과 일치하는 엔트리만 로드한다. 포맷 파싱은 결정적 로직(F20)에 속하며 Python 스크립트가 담당한다. (Phase 1 진입 조건 해소됨.)

### 미해결 2: 벤치마크 초기 골든셋 구성 방법

F22, F24에서 frozen 벤치마크 셋이 요구되지만, 초기 골든 라벨을 누가 어떻게 생성하는지 명시되지 않았다(사람 직접 레이블링 vs 과거 사이클 로그 추출). Phase 2 진입 시 결정 필요.

### 미해결 3: 스킬 목록 상한 수치

F19에서 "스킬 총 목록 상한"이 언급되지만 구체적인 수치가 합의되지 않았다. 현재 플러그인의 스킬 수(10개)를 기준으로 Phase 3 진입 전 결정 필요.

### 가정 1: pr-converge 트리거 시점

R2.5에서 "pr-converge가 CONVERGED+머지 시 호출"로 명시되었으나, 사용자가 머지를 승인하는 시점이 비동기적임을 고려해 sdd-orchestrator는 머지 이벤트 후 self-improve를 호출하는 방식으로 설계한다고 가정함. sdd-orchestrator Step 5의 현재 초안("머지·정리 완료 후")과 정합함을 확인.

### 가정 2: gh CLI 전제

pr-converge는 `gh` CLI가 인증된 GitHub 원격을 전제로 동작한다. 비-GitHub 원격(GitLab, Bitbucket 등)은 현재 범위 밖이며, 첫 패스에서 감지해 BLOCKED 보고 후 종료한다.

### 가정 3: 오에스컬레이션률 측정 방식

F23의 "오에스컬레이션률"(escalation이 필요하지 않았던 신호의 에스컬레이션 비율)은 사후 사람 검토로만 측정 가능하다. 자동 측정 방법은 Phase 2에서 설계한다.

---

BLOCKER_PASS

> sdd-blocker-checker 판정: Phase 2 진입 가능 (DONE_WITH_CONCERNS). 즉시 결정 필요했던 태그 포맷은 "해결 1"에서 확정. F23 자동/사후 지표 분리, NFR-4 명시적 task화 반영 완료. 미해결 2(벤치 골든셋)·미해결 3(스킬 상한)은 각각 Phase 2·Phase 3 진입 시 결정.
