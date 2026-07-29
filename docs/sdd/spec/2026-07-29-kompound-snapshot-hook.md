# kompound-snapshot-hook Spec

## 개요
- 한줄 요약: SDD 사이클이 만든 spec·설계(arch/ui/api/context)·result 문서를 사이클 종료 시점(T1)과 워크트리 삭제 직전(T2)에 자동으로 `marvelous_kompound/raw/`에 박제하고 `wiki/sdd-spec-registry.md`(+ `index.md` + `log.md`)를 갱신하는 훅.
- 타겟 사용자: SDD를 돌리는 개발자 본인(moon) + 다음 세션에서 kompound raw/registry를 참조하는 에이전트(자기 자신 포함, 미래 세션).
- 핵심 가치: 수동 스냅샷의 실패 모드는 "낡음"이 아니라 "빠짐"이며, 소실은 이미 실증됐다(`pattern-cpx-proto-improvements` 원본 전멸). 이벤트 트리거로 전환해 사람 의지에 의존하지 않는 자동 편입을 만든다.

이 spec은 새 설계를 제안하지 않는다. 설계는 `/Users/moon/workspace/marvelous_kompound/raw/sdd-kompound-snapshot-hook.md`(SSOT, 198줄, 사용자 승인 완료)에 이미 확정되어 있고, 아래 기능 요구사항은 그 설계를 EARS 표기로 번역한 것이다.

## 사용자 요구사항 (원문)

| # | 원문 | 출처 | → 기능 |
|---|------|------|--------|
| 1 | "모든 작업들이 끝나고 Kompound로 업데이트 하는 단계를 추가" | 사용자, 이번 요청 | F1, F2 |
| 2 | "수동 스냅샷의 실패 모드는 '낡음'이 아니라 '빠짐'이다. 이미 박제한 것은 잘 버텼지만, 새로 생긴 것이 registry에 편입되지 않았다." | design SSOT L20-21 | F1, F3 |
| 3 | "실측: 기존 44개 중 38개 바이트 동일 · drift 3건 vs 4주간 신규 feature 15 · result 28" | design SSOT L9-19 (표) | F1, F3 |
| 4 | "`pattern-cpx-proto-improvements`(spec+arch)는 6/30 스냅샷 당시 6개 워크트리 사본으로만 존재했고, 재스냅샷 시점에는 원본이 전부 사라져 kompound raw가 유일본이 됐다. 워크트리 삭제는 문서 삭제와 같다." | design SSOT L37-39 | F2, F3 |
| 5 | "박제는 `self-improve`와 나란히, 같은 지점에서 호출한다... 순서: 박제 먼저, self-improve 나중. self-improve는 하네스를 고칠 수 있으므로 박제가 그 뒤에 오면 실패 시 문서를 잃는다" | design SSOT L46-52 | F1 |
| 6 | "워크트리 삭제가 마지막 방어선이다." / "명령이 `git worktree remove` 또는 워크트리 디렉토리 `rm -rf`에 해당하면, 그 워크트리의 `docs/sdd` 아래 박제 대상 문서를 스캔해 kompound에 없는 것이 있으면 차단하고 박제 명령을 안내한다" | design SSOT L57, L61-63 | F2 |
| 7 | "차단이 과하면 경고 후 자동 박제 → 통과로 완화 가능. 다만 조용한 통과는 금지" | design SSOT L64-65 | F2, F11 |
| 8 | 포함/제외 대상 표 (`docs/sdd/` · `Docs/sdd/` 하위 spec/specs/design.arch/design.ui/design.api/context/result/development 포함, task/tasks·ORCHESTRATOR_STATE*·HANDOFF·GUIDE·DESIGN.md·test-guide-* 제외, 워크트리 필수 스캔) | design SSOT L71-79 | F3 |
| 9 | 네이밍 규칙(`raw/<project>-<feature>-<kind>.md`, kind 매핑, 프리픽스 10종 고정 매핑, 날짜/접미사 제거, `<project>-<project>` 중복 접기) | design SSOT L81-108 | F4 |
| 10 | dedup 규칙(md5 그룹핑, canonical = non-worktree 우선→경로 짧은 것 우선, 단 내용 상이 시 별개 문서로 최신 채택) | design SSOT L110-117 | F5 |
| 11 | 멱등성 규칙(없으면 신규 복사 / 같으면 무동작·무로그 / 다르면 덮어쓰고 갱신 카운트) | design SSOT L119-124 | F6 |
| 12 | registry 갱신 범위(신규 feature 행 추가, 새 kind 열 교체, 헤더 카운트 갱신, index.md Entries+최근변경, log.md 1줄) + "위 4개 파일 외에 다른 wiki/*.md는 건드리지 않는다" | design SSOT L128-138 | F7 |
| 13 | 검증 게이트 3종(링크 무결성 / 양방향 카운트 일치 / raw flat 유지), "박제 후 반드시 확인하고, 실패하면 커밋하지 않는다" | design SSOT L140-147 | F8 |
| 14 | "훅은 커밋되지 않은 변경을 발견하면 스스로 커밋하지 말고 중단·보고해야 한다. 남의 작업을 임의로 커밋하는 것이 더 위험하다" | design SSOT L182-185 | F9 |
| 15 | "index.md / log.md 동시 편집 충돌... 해소는 '양쪽 보존'이 정답" | design SSOT L186-187 | F10 |
| 16 | "훅이 조용히 실패한다. 박제 0건으로 끝났을 때 '변경 없음'과 '스캔 실패'를 구분해 보고해야 한다. 조용한 0건이 가장 위험하다" | design SSOT L188-189 | F11 |
| 17 | "`pptx-template/Docs/sdd guide/`처럼 이름만 sdd인 디렉토리가 있다. 프리픽스 매핑에 없는 repo는 박제하지 말고 경고만 낸다" | design SSOT L190-191 | F12 |
| 18 | 결정적 코어는 Python stdlib-only, 네트워크/LLM 무호출, fail-safe. `hooks/lib/` 아래 패키지 (moon-harness CLAUDE.md 결정↔판단 분리 원칙) | 컨트롤러 지시 | F13 |
| 19 | T2 게이트는 기존 `hooks/enforcement/worktree-add-gate.sh`와 같은 자리·같은 패턴으로 `hooks/hooks.json` PreToolUse/matcher:Bash에 등록 | design SSOT L59-60, 컨트롤러 지시 | F14 |
| 20 | "주제별 위키 페이지 합성 — 사람이 `/ingest`로 판단 / task 문서 박제 / home repo 쪽 문서 수정 — 훅은 kompound에만 쓴다(단방향)" | design SSOT L195-197 | 범위 밖 |
| 21 | "moon-harness는 범용 Claude Code 플러그인이다... 레포 특화 하드코딩 금지(하네스는 범용)" — blocker-checker가 스캔 루트·kompound 경로·프리픽스 매핑의 사용자 고유 값 하드코딩을 BLOCKED로 판정 | moon-harness CLAUDE.md, 컨트롤러 blocker-checker 피드백 | F16 |
| 22 | "tdd방식에 맞게 refactor test를 작성하고 작업에 들어가는것도 추가할까? 그게 안전하려나" — `hooks/enforcement/stop-pipeline.py`(~450줄, protected set)에 행위 테스트 0개 상태에서 D2에 따라 신규 라벨 분기를 넣는 것이 최대 리스크라는 실측(533 passed, stop-pipeline.py 커버 0) 기반 사용자 요청 | 사용자, 이번 요청 | F17 |

## 기능 요구사항

### F1: T1 — SDD Phase 4 종료 시 정상 경로 박제

**삽입 지점 (사용자 확정 2026-07-29)**: `skills/sdd-orchestrator/SKILL.md` Step 4의 **4-2(`ORCHESTRATOR_STATE.md` 상태를 COMPLETED로 변경) 직후**, 4-3(push + pr-converge) 이전.

> 근거(사용자): "4-3은 대부분 의도를 바꾸는 게 아니라 코드단의 수정이야. 보통 4-2가 끝나면 의도가 잘못되어서 수정하는 경우는 없어." 즉 박제 대상인 spec·설계·result 문서의 **의도는 4-2에서 확정**되고, 이후 pr-converge 수렴은 코드 레벨 변경이다. 이 지점은 설계 SSOT의 세 전제(① result 생성 이후 ② 워크트리 생존 ③ self-improve보다 먼저)를 모두 만족한다. 설계 SSOT가 문자 그대로 지정한 "self-improve 호출부 옆"(Step 5)은 현행 SKILL.md에서 Step 4-5(worktree 정리)보다 뒤이므로 전제 ②를 위반한다 — 그래서 채택하지 않는다.

**강제 수준 (사용자 확정 2026-07-29)**: 프롬프트 지시가 아니라 **`hooks/enforcement/stop-pipeline.py`의 라벨 directive로 결정적으로 강제**한다.

> 근거: 이 feature의 동기 자체가 "사람/에이전트의 성실성에 의존하지 않는다"이므로, SKILL.md 산문 지시만으로는 에이전트가 건너뛸 수 있어 동기와 상충한다. T1(정상 경로)과 T2(안전망)를 **모두 결정적으로 강제**해 이중화한다.

> (정정, architect-reviewer 2026-07-29) D2의 의도(결정적 강제)는 유지된다. 다만 실현 수단은 **라벨 전진 차단이 아니라 Stop 차단**이다 — `advance_label`(`hooks/enforcement/lib/pipeline-utils.sh:81`)은 bash 함수이며 `stop-pipeline.py`에 존재하지 않고, `DIRECTIVES`의 마지막 키가 `PHASE4_WORKTREE_CREATED`라 Phase 4 시점에는 "다음 라벨" 자체가 구조적으로 없다. 강제는 Stop 훅에서 `decide()`가 박제 미완 시 `{"decision": "block"}`을 반환하는 방식으로 구현된다.

- WHEN `ORCHESTRATOR_STATE.md` 상태가 `COMPLETED`가 되었을 때 THE SYSTEM SHALL Stop 훅이 kompound 박제를 지시하는 directive를 주입하고, 박제 완료가 확인될 때까지 **Stop을 차단한다(다음 턴 진행 차단)**.
- THE SYSTEM SHALL 박제 완료 여부를 파이프라인 상태(신규 라벨 또는 그에 준하는 상태 필드)로 기록하여, 재진입 시 중복 실행 없이 멱등하게 판정한다.
- WHEN 동일 사이클에서 `Skill(self-improve)` 호출(Step 5)이 예정되어 있을 때 THE SYSTEM SHALL 박제 실행을 self-improve 호출보다 먼저 완료한다.
- THE SYSTEM SHALL 박제 단계를 self-improve 호출 조건(`.harness/LEARNING.md` 신규 엔트리 유무)과 **독립적으로** 실행한다(self-improve를 건너뛰어도 박제는 실행됨).
- IF 박제가 실패하면 THEN THE SYSTEM SHALL 실패를 사용자에게 보고하되 SDD 사이클 완료 자체를 영구 차단하지 않는다(재시도 안내 후 사용자 판단 — 소실 방어는 T2가 이중으로 담당한다).
- Acceptance:
  - `hooks/enforcement/stop-pipeline.py`에 4-2 완료 시점에 대응하는 라벨/상태 분기와 박제 directive 문자열이 존재하고, 해당 분기를 커버하는 오프라인 pytest 케이스가 `tests/` 아래에 존재한다.
  - 박제 미완(`pending ≥ 1`) 상태에서 Stop 훅이 발화하면 `decide()`가 `{"continue": true}`를 반환하지 않고 `{"decision": "block"}` + 박제 directive를 반환함을 검증하는 테스트가 존재한다. 박제 완료(`pending == 0`) 또는 kompound 미설정 시에는 즉시 통과함을 검증하는 대칭 테스트도 존재한다.
    - (주) `advance_label`(`hooks/enforcement/lib/pipeline-utils.sh:81`)은 이 게이트의 대상이 아니다 — Phase 4 시점의 `current_label`은 이미 터미널 `PHASE4_WORKTREE_CREATED`이며 그 이후 라벨 전이가 존재하지 않는다. 강제는 라벨 전진 차단이 아니라 **Stop 차단**으로 구현된다.
  - `skills/sdd-orchestrator/SKILL.md` Step 4에 박제 스텝이 4-2와 4-3 **사이**에 문서화되어 있고, 그 텍스트가 Step 5 self-improve 호출 텍스트보다 앞선 줄 번호에 위치한다.
  - 동일 사이클에서 훅을 2회 실행했을 때 두 번째 실행이 "이미 박제됨"으로 무동작 판정됨을 검증하는 테스트가 존재한다.
  - kompound 저장소 경로가 F16의 해석 순서 어디서도 해석되지 않는 환경을 시뮬레이션했을 때, T1이 "무동작 통과"로 종료되어 SDD 사이클 완료를 영구 차단하지 않음을 검증하는 테스트가 존재한다(F16과 연동).
  - `hooks/enforcement/stop-pipeline.py`에 대한 위 라벨/directive 분기 수정은 F17의 회귀 안전망이 GREEN으로 확인된 뒤에만 시작한다(F17 참조).
  - 카탈로그 갱신만 실패하고 raw 복사는 성공한 상태에서, 다음 Stop 훅 발화가 **재차 차단하지 않고 블록 예산도 소모하지 않음**을 검증하는 테스트가 존재한다(차단 전후의 예산 값 비교로 단정). 카탈로그 재시도는 T1이 아니라 다음 사이클의 카탈로그 단계·T2 자동박제·수동 실행이 담당한다.

### F2: T2 — 워크트리 삭제 직전 안전망 게이트

**차단 정책 (사용자 확정 2026-07-29)**: **자동 박제 시도 → 성공 시 경고 후 통과 / 실패 시에만 차단.**

> 근거: T2가 막으려는 것은 "박제 실패"가 아니라 "박제가 아예 시도되지 않은 문서의 존재"다. T1이 결정적으로 강제되므로 완주한 사이클은 이미 커버되고, T2에 남는 것은 중단된 사이클 · SDD 밖에서 만든 문서 · 프리픽스 미등록 repo · T1 이후 추가된 문서다. 이때 자동 박제가 성공하면 흐름을 끊을 이유가 없고, 실패하는 경우(F9 dirty/diverge — 2026-07-28 실측 · F12 프리픽스 미등록)에만 차단하면 "조용한 통과 금지"를 지키면서 정상 경로를 방해하지 않는다. 즉 실사용상 **평소엔 항상 통과, 실측된 예외에서만 차단**으로 동작한다.

> (정정, architect-reviewer 3차 2026-07-29 — A-5 채택) 박제(`apply`)는 **(i) raw 복사**와 **(ii) 카탈로그 갱신**(registry+index+log, F7·F8)의 2단으로 분리된다. **T2 차단 = (i) 실패만.** 차단 사유 집합: `scan_error` · F9 `precondition_failed`(dirty/diverge) · F12 `unmapped_blocking`(프리픽스 미등록) · **raw 복사 실패(`write_failed`)** · `busy`. **F8 검증 게이트 실패**와 **카탈로그 파싱 실패(`catalog_unparsed`)**는 더 이상 차단 사유가 아니며 **경고 후 통과**한다 — registry 파싱/게이트 실패는 "문서가 위험하다"가 아니라 "카탈로그 갱신 방법을 모른다"이고, T2의 목적(raw 보존)은 (i)의 성공으로 이미 달성되었기 때문이다. **커밋 경계**: (i) 성공 시 raw를 즉시 커밋해 워킹트리를 clean하게 유지한다(F9 dirty 판정과의 자기오염 회피). (ii) 실패 시 카탈로그 변경만 롤백하고 **raw는 유지**한다 — 다음 실행은 (ii)만 재시도한다.

- WHEN Bash 명령이 `git worktree remove <path>` 패턴에 매칭될 때 THE SYSTEM SHALL 해당 워크트리의 `docs/sdd`(및 `Docs/sdd`) 하위 박제 대상 문서를 스캔한다.
- WHEN Bash 명령이 워크트리 디렉토리를 대상으로 하는 재귀 삭제(`rm -rf <worktree-path>` 등)에 매칭될 때 THE SYSTEM SHALL 동일한 스캔 로직을 적용한다.
- IF kompound 저장소 경로가 F16의 해석 순서로 해석되지 않으면 THEN THE SYSTEM SHALL 스캔·박제 시도를 건너뛰고 명령을 통과시킨다(`gate_pass`) — 기능 비활성화이지 차단 대상이 아니다.
- IF 스캔 결과 미박제 문서가 0건이면 THEN THE SYSTEM SHALL 명령을 통과시키고 통과 사유를 로그에 남긴다(`gate_pass` 패턴).
- IF 미박제 문서가 1건 이상이면 THEN THE SYSTEM SHALL **먼저 F9(kompound dirty/diverge 상태)를 확인**한 뒤에만 apply의 **(i) raw 복사** 단계로 진행한다. kompound가 dirty이거나 diverge 상태이면 그 자체로 (i) 단계를 실패(`precondition_failed`)로 간주하고, 아래 "(i) raw 복사 단계 자체가 실패하면" 분기로 즉시 넘어간다((i)를 실행조차 하지 않는다).
- IF (F9 확인 통과 후) apply의 **(i) raw 복사**가 성공하면 THEN THE SYSTEM SHALL raw를 **즉시 커밋**해 워킹트리를 clean하게 유지한 뒤, 이어서 **(ii) 카탈로그 갱신**(registry+index+log, F7·F8) 단계로 진행한다.
- IF (ii) 카탈로그 갱신이 성공하면 THEN THE SYSTEM SHALL 박제된 문서 목록을 **경고로 출력한 뒤 명령을 통과**시킨다.
- IF (ii) 카탈로그 갱신이 실패하면(F8 검증 게이트 실패 또는 카탈로그 파싱 실패 `catalog_unparsed`) THEN THE SYSTEM SHALL 카탈로그 변경만 롤백하고(이미 커밋된 raw는 그대로 유지한다), 그 사실을 **경고로 출력한 뒤 명령을 통과**시킨다 — (i)에서 raw 보존이라는 T2의 목적이 이미 달성되었으므로 카탈로그 실패가 워크트리 삭제를 막지 않는다. 다음 실행은 (ii) 카탈로그 갱신만 재시도한다.
- IF (i) raw 복사 단계 자체가 실패하면(`precondition_failed` 또는 `write_failed`) THEN THE SYSTEM SHALL `exit 2`로 명령을 차단하고 실패 사유(F9 dirty/diverge 파일 목록 / raw 복사 실패(`write_failed`) 상세 / F12 미등록 프리픽스 repo 경로(`unmapped_blocking`))와 수동 박제 방법을 안내한다.
- Acceptance:
  - `hooks/enforcement/<신규-게이트-스크립트>.sh`가 `hooks/enforcement/worktree-add-gate.sh`와 동일한 골격(INPUT 파싱 → tool_name 확인 → command 확인 → 관련 명령만 처리 → 차단/통과)을 따른다.
  - `hooks/hooks.json`의 `PreToolUse`/`matcher: "Bash"` 배열에 신규 게이트가 `worktree-add-gate.sh`와 같은 블록 내 항목으로 등록되어 있다.
  - 차단 시 종료 코드가 기존 게이트와 동일하게 `exit 2`이고 `gate_block`을 호출한다.
  - "조용한 통과"가 없다 — 통과 경로도 반드시 `gate_pass` 로그 호출을 거친다(미박제 0건이든, 자동 박제 성공 후든, kompound 미설정이든).
  - 게이트는 미박제 판정 및 박제 실행을 **F13의 Python 결정적 코어를 서브프로세스로 호출**해 수행한다(스캔·네이밍·dedup 로직을 bash에 중복 구현하지 않는다). 판정 전용 호출은 부작용이 없는 확인 모드(예: `check` 서브커맨드)를 사용한다 — 구체 인터페이스(플래그 vs 서브커맨드)는 architect 결정 사항이며, spec은 "부작용 없는 판정 전용 호출 경로가 존재해야 한다"만 요구한다.
  - kompound dirty 상태를 fixture로 주입했을 때, 게이트가 (i) raw 복사를 시도하지 않고(부작용 없음) 바로 `exit 2` 실패 분기(`precondition_failed`)로 진입함을 검증하는 테스트가 존재한다(F9 선행 확인).
  - kompound 경로 미설정 환경에서 게이트가 `gate_pass`로 종료됨을 검증하는 테스트가 존재한다(F16 연동).
  - **자동박제 성공 통과 분기의 하위 경로 — "raw만 성공(카탈로그 뒤처짐)"**: (i) raw 복사는 성공해 즉시 커밋되지만 (ii) 카탈로그 갱신이 F8 검증 게이트 실패 또는 `catalog_unparsed`로 실패하는 fixture에서, raw 커밋은 유지되고 카탈로그 변경만 롤백되며 명령이 **차단되지 않고 경고 후 통과**함을 검증하는 테스트가 존재한다(A-5 커밋 경계).
  - 위 5개 분기 — **kompound 미설정 통과 / 0건 통과 / 자동박제 성공 통과(하위: (i)(ii) 모두 성공 · **raw만 성공·카탈로그 뒤처짐**(F8·`catalog_unparsed`) — 둘 다 경고 후 통과) / (i) raw 복사 실패 차단(F9 `precondition_failed` · `write_failed` · F12 `unmapped_blocking`) / 무관한 Bash 명령 무개입** — 각각을 커버하는 테스트가 존재한다. **F8 검증 게이트 실패는 이 분기 집합에서 차단 사유가 아니다**(성공 통과 분기의 하위 경로로만 등장).

### F3: 수집 스코프 — 포함/제외 디렉토리 및 워크트리 스캔
- THE SYSTEM SHALL F16으로 주입된 **스캔 루트** 하위를 전수 스캔하되, `docs/sdd/` 또는 `Docs/sdd/` 경로 아래 `spec/` `specs/` `design/arch/` `design/ui/` `design/api/` `context/` `result/` `development/` 디렉토리만 대상으로 삼는다. 스캔 루트 값은 코드에 하드코딩하지 않는다(현재 사용자 환경의 실제 값은 "결정 기록 — 현재 환경 기준값" 참조).
- THE SYSTEM SHALL `task/` `tasks/` 디렉토리, `ORCHESTRATOR_STATE*.md`, `HANDOFF.md`, `*-GUIDE.md`, `DESIGN.md`, `test-guide-*.md` 파일을 스캔 대상에서 제외한다.
- THE SYSTEM SHALL `*/worktrees/*` 경로도 스캔 대상에 포함한다(워크트리 전용 문서가 실제로 존재하기 때문).
- WHERE 스캔 경로에 `.git` `node_modules` `build` `ExternLib` `.venv` `venv` 디렉토리가 포함될 때 THE SYSTEM SHALL 해당 서브트리를 순회하지 않는다.
- Acceptance: 참고 구현(design SSOT L153-178)의 `KINDS` / `SKIP_DIRS` / `SKIP_NAMES` 상수와 매칭 로직을 그대로 이식한 유닛 테스트가 `tests/`에 존재하며, `task/` 하위 md·`HANDOFF.md`·`ORCHESTRATOR_STATE.md`가 스캔 결과에서 0건임을 검증한다.

### F4: 네이밍 — raw 파일명 생성 규칙
- THE SYSTEM SHALL 각 수집 문서를 `raw/<project>-<feature>-<kind>.md` 형식으로 명명한다.
- THE SYSTEM SHALL `kind`를 `spec|specs→spec`, `arch→arch`, `ui→ui`, `api→api`, `result→result`, `context→context`, `development→arch`로 매핑한다.
- THE SYSTEM SHALL `<project>` 프리픽스를 F16으로 주입되는 **매핑 데이터**(코드 리터럴이 아닌 설정)로 결정한다. 다음은 그 **기본 매핑**(설정으로 교체·확장 가능)이다: `Marvelous`/`Marvelous_dev`/`Marvelous_feature`/`Marvelous_code_review`/`auto-fix-base`→`marvelous`, `CLOFab_Web`(하위 `clofab/` 포함)→`clofab`, `Marvelous_graphify`→`graphify`, `auto-fix-orchestrator`→`autofix`, `crash-ai-analysis`→`crashai`, `codegraph-clo`→`codegraph`, `ai-code-reviewer-action`→`aireview`, `moon-harness`→`harness`, `rein`→`rein`, `claude-slack-channel`→`slack`.
- THE SYSTEM SHALL 원본 파일명의 날짜 프리픽스(`YYYY-MM-DD-`)와 `-spec`/`-dev`/`-result` 접미사를 제거한 나머지를 `<feature>`로 사용한다.
- IF 생성된 이름이 `<project>-<project>-...` 꼴(프리픽스 중복)이면 THEN THE SYSTEM SHALL 중복된 프리픽스 하나를 접어 예: `codegraph-codegraph-internal-mcp-result` → `codegraph-internal-mcp-result`로 만든다.
- Acceptance: 위 매핑표를 데이터로 갖는 순수 함수에 대해 최소 10개 프리픽스 각각과 `<project>-<project>` 중복 케이스 1건 이상을 커버하는 pytest 케이스가 통과한다. 프리픽스 매핑에 없는 repo 입력 시 예외 없이 "미등록" 신호를 반환한다(F12와 연동).

### F5: dedup — md5 그룹핑과 canonical 선택
- THE SYSTEM SHALL 동일 `(kind, md5)` 조합으로 문서를 그룹핑한다.
- WHEN 한 그룹에 경로가 2개 이상일 때 THE SYSTEM SHALL canonical 경로를 "non-worktree 우선 → 경로 문자열 길이가 짧은 것 우선" 순으로 정렬해 첫 번째로 선택한다.
- IF main repo 사본과 워크트리 사본의 내용(md5)이 서로 다르면 THEN THE SYSTEM SHALL 이들을 별개 문서로 취급하고, 최신(파일시스템 mtime 기준 더 최근)본을 채택한다.
- Acceptance: 참고 구현 정렬 키 `("worktrees" in x, len(x))`를 그대로 사용하는 함수에 대해, (a) 동일 해시 3사본(main 1 + worktree 2) 입력 시 non-worktree가 선택됨 (b) 동일 해시 worktree 2사본만 입력 시 짧은 경로가 선택됨 (c) 해시가 다른 main/worktree 쌍 입력 시 별개 문서 2건으로 반환됨을 검증하는 pytest 케이스가 존재한다.

### F6: 멱등성 — 재실행 시 무변경 보장
- IF 대상 `raw/<name>.md`가 존재하지 않으면 THEN THE SYSTEM SHALL 신규 파일로 복사하고 "신규" 카운트를 증가시킨다.
- IF 대상이 존재하고 내용(md5)이 동일하면 THEN THE SYSTEM SHALL 파일을 변경하지 않고, 로그(log.md/실행 리포트 어느 쪽에도)에 해당 파일에 대한 엔트리를 남기지 않는다.
- IF 대상이 존재하고 내용이 다르면 THEN THE SYSTEM SHALL 파일을 덮어쓰고 "갱신" 카운트를 증가시킨다.
- Acceptance: 동일 스캔을 연속 2회 실행했을 때 두 번째 실행에서 "신규"/"갱신" 카운트가 모두 0이고 `git status --porcelain -- raw/`가 빈 문자열임을 확인하는 테스트(또는 그에 준하는 순수함수 검증)가 존재한다.

### F7: registry / index / log 갱신 — 범위 고정
- WHEN 박제 스캔 결과 신규 또는 갱신된 raw가 1건 이상일 때 THE SYSTEM SHALL `wiki/sdd-spec-registry.md`, `wiki/index.md`, `wiki/log.md` 세 파일만 갱신한다.
- THE SYSTEM SHALL `sdd-spec-registry.md`에서: 신규 feature는 해당 프로젝트 표에 행 추가(프로젝트 표 자체가 없으면 표 신설), 기존 feature의 새 kind는 해당 열의 `—`를 링크로 교체, 헤더의 "N feature · raw M개" 카운트를 갱신한다.
  - **표 신설 예외(architect-reviewer 실측)**: 단, 해당 프로젝트가 `프로젝트` 열을 가진 통합 표(예: "그 외 프로젝트")에 이미 행으로 존재하면, 새 프로젝트 전용 표를 신설하지 않고 그 통합 표에 행을 추가한다. 예: `moon-harness`는 자기 전용 표가 없고 "그 외 프로젝트" 통합 표의 행으로 존재하므로, moon-harness의 신규 feature도 그 통합 표에 행을 추가해야 한다(새 표를 만들면 기존 3개 moon-harness 행과 분열된다).
  - **열 추가 정책(사용자 승인, ③ 반전 — architect-reviewer 3차)**: 대상 표에 신규 kind에 해당하는 열 자체가 없으면(기존 문구는 "열이 있고 그 칸이 `—`인 경우"만 다뤘다), THE SYSTEM SHALL **열을 추가하고 기존 행의 그 칸을 `—`로 채운다**. 안전 조건 2개를 모두 만족해야 한다: (a) 추가할 kind가 6종(`spec`/`arch`/`ui`/`api`/`context`/`result`) 이내일 것 (b) 대상 표가 "인지된 형상"(기존 열 구성이 파서가 이해하는 패턴) 이내일 것. IF 안전 조건을 충족하지 못하면 THEN THE SYSTEM SHALL 카탈로그 갱신 실패(`catalog_unparsed`)로 보고하되, **raw 보존과 명령 통과에는 영향을 주지 않는다**(F2의 커밋 경계 참조 — (i) raw 복사는 이미 커밋되어 있고 (ii)만 실패한다).
  - **카운트 갱신 대상의 구체화**: 갱신 대상은 (a) "현재 상태" 문장의 총 feature/raw 수 및 kind별 분해(`spec N · arch N · result N · api N · ui N · context N`), (b) 헤더의 "N feature · raw M개" 문장이다. **다음은 갱신하지 않는다(불변)**: 날짜가 박힌 과거 스냅샷 서술(예: `**2026-07-28 재스냅샷**: 40 feature · raw 117개` — 역사 서술이므로 갱신하면 사실 왜곡), 그리고 각 프로젝트 섹션 내 개별 서술 카운트(예: "8 feature 전부 spec·arch·result 완비"). 스캔 중 위 두 범주(갱신 대상 vs 불변) 어디에도 속하지 않는 카운트 문장을 발견하면, 임의로 판단해 고치지 않고 실패로 보고한다.
- THE SYSTEM SHALL `wiki/index.md`의 Entries 중 `sdd-spec-registry` 훅 문장과 최근 변경 섹션에 이번 배치를 prepend한다.
- THE SYSTEM SHALL `wiki/log.md`에 이번 배치 전체를 요약한 한 줄만 append한다(배치 1건 = 로그 1줄, AGENTS.md Bulk Ingest Brief 규칙).
- IF 이번 실행에서 박제된 raw가 0건이면 THEN THE SYSTEM SHALL registry/index/log 갱신과 F8의 검증 게이트 3종 실행을 **모두 스킵**하고, "변경 없음"으로 보고한다(F11의 "무동작"과 일관 — 단 F11이 요구하는 "변경 없음" vs "스캔 실패" 구분 보고는 반드시 수행한다. 스킵은 정상 종료이지 실패가 아니다).
- Acceptance: 위 4개 파일(registry, index, log, 그리고 raw 자신) 외에 kompound 저장소의 `wiki/*.md`가 diff에 나타나면 실패로 판정하는 검증 스텝이 존재한다(`git diff --name-only -- wiki/` 결과가 이 3개 파일 집합의 부분집합인지 확인, kompound 저장소 경로는 F16으로 주입). 박제 0건 케이스에서 registry/index/log 어느 것도 diff에 나타나지 않고 F8의 3종 게이트 호출 자체가 스킵됨(호출 로그 0건)을 검증하는 테스트가 존재한다. moon-harness처럼 통합 표에 행으로만 존재하는 프로젝트에 신규 feature를 주입했을 때, 신규 전용 표가 생성되지 않고 기존 통합 표에 행이 추가됨을 검증하는 테스트가 존재한다. 날짜가 박힌 과거 스냅샷 서술 문자열이 갱신 전/후 바이트 동일함을 검증하는 테스트가 존재한다. **6열 표에 `ui` 열을 추가할 때 기존 행의 그 칸이 `—`로 채워지고 다른 열·다른 줄은 바이트 불변임을 검증하는 테스트가 존재한다.** 안전 조건(6종 이내 / 인지된 표 형상 이내)을 벗어난 fixture에서 `catalog_unparsed`로 실패 보고되지만 raw 커밋과 명령 통과(F2)에는 영향이 없음을 검증하는 테스트가 존재한다.

### F8: 검증 게이트 3종 — 커밋 전 필수 통과
- THE SYSTEM SHALL 박제 실행 후 커밋 전에 다음 3개 게이트를 순서대로 실행한다: (1) 링크 무결성 — registry가 가리키는 **스냅샷 집합(아래 모집단 한정 참조) 링크**가 실재 파일을 가리킴, (2) 양방향 카운트 일치 — registry가 가리키는 스냅샷 집합 링크 집합과 `raw/` 중 **`prefix_map`의 값**(설정 병합 후 유효 프리픽스 집합, `null` 제거)과 kind 접미사(spec/arch/ui/api/context/result)를 모두 만족하는 파일 집합 사이의 **양방향 차집합이 0**(단순 개수 비교가 아니다 — 누락 1건과 유령 링크 1건이 상쇄되어 통과하는 것을 막는다), (3) flat 유지 — `raw/` 하위에 `assets/` 외 디렉토리가 생성되지 않음.
  - **게이트 (2) — "양방향 카운트 일치"는 설계 SSOT 용어라 항목명은 유지하되 정의를 차집합으로 강화한 근거(architect-reviewer 2차)**: "링크 수 == 파일 수"라는 단순 개수 비교는 **상쇄 오류를 통과시킨다** — registry에서 실재 링크 A가 빠지고 동시에 존재하지 않는 유령 링크 B가 생기면 개수는 같지만 집합은 다르다. 게이트 (1)은 "링크 → 파일 존재" 방향만 검사하므로 "raw에는 있지만 registry에 링크되지 않은 파일"(=이 훅의 존재 이유인 "빠짐")을 잡지 못한다. 따라서 게이트 (2)는 registry 링크 집합과 raw 스냅샷 파일 집합의 **양방향 차집합이 정확히 0**임을 요구한다.
  - **모집단 한정 근거(architect-reviewer 실측, `/Users/moon/workspace/marvelous_kompound`)**: 단순히 "kind 접미사로 끝나는 raw 파일"을 모집단으로 삼으면 registry 링크 117건 vs 122건으로 **항상 불일치**한다. 초과 5건(`clocv-wasm-api-expansion-spec` / `fabric-creator-web-api-spec` / `gps-html-to-ui` / `mvcv-refactor-lock-fixture-spec` / `pattern-api-json-external-spec`)은 SDD 스냅샷이 아니라 독립적으로 `/ingest`된 주제 문서가 우연히 kind 접미사로 끝난 것이다. 모집단을 `prefix_map`의 값(설정 병합 후 유효 프리픽스 집합, `null` 제거) ∩ kind 접미사로 한정하면 117건이 되어 registry 링크와 양방향 차집합 0으로 정확히 일치한다. 이 한정은 F12(프리픽스 미등록 repo는 애초에 박제되지 않음)와 정의가 일관된다 — 미등록 프리픽스 문서는 이 훅이 만든 raw가 아니므로 모집단에 들어갈 이유가 없다.
  - **게이트 (1) 검사 범위 한정 근거(architect-reviewer 2차 — C-1과 동일 구조 함정)**: "registry가 가리키는 모든 `../raw/*.md` 링크"를 검사 범위로 두면, 사람이 `/ingest`한 주제 문서(이 훅이 만들지 않은 raw)를 삭제하고 registry 링크만 남기는 순간 게이트 (1)이 실패해 T2가 `exit 2`로 **모든** `git worktree remove`를 차단하게 된다 — 우리가 만들지 않은 링크의 결함이 워크트리 삭제를 막는 것과 동일한 함정 구조다. 따라서 게이트 (1)의 검사 범위도 게이트 (2)와 같은 **스냅샷 집합(모집단 한정)** 링크로 한정한다. 오늘 기준으로는 registry 링크가 모두 실재해 즉시 게이트 실패로 이어지지는 않으나, 위는 구조적 함정이므로 지금 한정해둔다.
- WHERE 박제된 raw가 0건일 때(F7 참조) THE SYSTEM SHALL 위 3개 게이트를 실행하지 않는다 — 갱신 대상이 없으므로 게이트 스킵은 실패가 아니라 정상 종료다.
- IF 3개 게이트 중 하나라도 실패하면 THEN THE SYSTEM SHALL **카탈로그 커밋을 하지 않고**(이미 커밋된 raw는 그대로 유지한다 — apply의 (i)/(ii) 커밋 경계, F2 참조) 실패 게이트명과 사유를 보고한다. F8 실패는 F2의 T2 차단 사유가 아니다 — raw가 이미 (i)에서 커밋되어 워크트리 삭제를 막을 이유가 없으므로, F8 실패는 T2를 차단하지 않고 경고 후 통과로 이어진다(F2 참조).
- Acceptance: 게이트 (1)(2)(3) 각각을 독립적으로 실패시키는 3개의 fixture(끊긴 링크 1건 주입 / 카운트 불일치 1건 주입 / `raw/` 하위 서브디렉토리 1건 주입)에 대해 실행 결과가 "카탈로그 커밋 안 함 + raw 커밋은 유지 + 실패 게이트명 보고"임을 검증하는 pytest가 존재한다. 박제 0건 케이스에서 3개 게이트 함수가 호출되지 않음(mock call count 0)을 검증하는 테스트가 존재한다. **게이트 (2)에 프리픽스 미등록 repo에서 유래한(kind 접미사만 우연히 일치하는) raw 파일을 fixture로 섞어 넣었을 때 모집단 집계에서 제외되어 게이트가 여전히 통과함을 검증하는 테스트가 존재한다**(모집단 한정 로직 검증). **게이트 (2)에 "개수는 같고 집합은 어긋나는" 교차 케이스(누락 링크 1건 + 유령 링크 1건을 동시에 주입해 카운트는 동일하지만 양방향 차집합은 비지 않는 fixture)를 추가해, 단순 개수 비교로는 놓치는 실패를 차집합 검사가 정확히 잡음을 검증하는 테스트가 존재한다.** 게이트 (1)의 검사 범위가 스냅샷 집합으로 한정되어, 프리픽스 미등록 repo 유래 raw나 사람이 `/ingest`한 주제 문서를 가리키는 registry 외부 링크가 깨져도 게이트 (1)이 실패하지 않음을 검증하는 테스트가 존재한다.

### F9: 실패 모드 — kompound dirty/diverge
- IF kompound 워킹트리에 커밋되지 않은 변경(`git status --porcelain` non-empty)이 있으면 THEN THE SYSTEM SHALL 박제를 실행하지 않고(또는 실행 후 커밋하지 않고) 중단하며, 어떤 파일이 dirty한지 보고한다.
- IF kompound가 원격과 diverge 상태(`git pull --ff-only`가 실패하는 상태)이면 THEN THE SYSTEM SHALL 자동 rebase/merge를 시도하지 않고 중단·보고한다.
- Acceptance: dirty 상태를 시뮬레이션한 fixture에서 훅 실행 결과가 "커밋 0건 + 중단 사유에 dirty 파일 목록 포함"임을 검증하는 테스트가 존재한다.

### F10: 실패 모드 — index.md/log.md 동시 편집 충돌
- IF `wiki/index.md` 또는 `wiki/log.md`에 대한 갱신이 사람/다른 프로세스의 동시 편집과 충돌하면 THEN THE SYSTEM SHALL 자동 병합을 "양쪽 보존" 전략으로 처리한다 — `log.md`는 시간순 append이므로 두 변경을 모두 append하고, `index.md`의 최근 변경 섹션은 newest-first로 두 항목 모두 보존한다.
- Acceptance: 사양 문서에 "양쪽 보존" 전략이 텍스트로 명시되어 있고, 최소 하나의 통합 테스트(또는 수동 검증 절차 기술)로 두 항목이 유실 없이 모두 남는지 확인한다.

### F11: 실패 모드 — 조용한 0건 금지
- WHEN 박제 스캔이 0건(신규 0, 갱신 0)으로 종료될 때 THE SYSTEM SHALL "변경 없음"(스캔은 정상 완료, 대상이 실제로 없었음)과 "스캔 실패"(예외/권한 오류 등으로 스캔 자체가 조기 종료)를 구분하여 보고한다.
- IF 스캔 중 예외가 발생하면 THEN THE SYSTEM SHALL 0건으로 조용히 종료하지 않고 실패로 명시 보고한다.
- Acceptance: 정상 완료 0건 케이스와 예외 발생 케이스 각각에 대해 반환되는 상태 코드/메시지가 서로 다른 값임을 검증하는 pytest가 존재한다(둘 다 "0건"이라는 동일 문자열로 뭉뚱그려지면 실패).

### F12: 프리픽스 미등록 repo — 경고만, 박제 금지
- IF 스캔된 문서의 repo 경로가 F4/F16의 프리픽스 매핑(기본값 또는 설정으로 교체된 값)에 없으면 THEN THE SYSTEM SHALL 해당 문서를 박제하지 않고 경고 메시지(repo 경로 포함)만 출력한다.
- **`pending`/`unmapped` 카운터 분리(architect-reviewer 지적)**: THE SYSTEM SHALL 미박제 문서 카운트를 두 개로 분리해 집계한다 — `pending`(프리픽스가 **매핑된** 미박제 문서 수)과 `unmapped`(프리픽스 **미등록** 문서 수, 별도 카운터). 프리픽스 미등록 문서를 `pending`에 합산하지 않는다.
  - 근거: 미등록 프리픽스 문서는 F12 규칙상 영원히 박제될 수 없다. 이를 `pending`에 포함시키면 F1(T1)의 Stop 차단 조건이 이 문서 때문에 매 사이클 반복 발화하지만 F12가 박제를 금지하므로 영구 미해소 상태(무한 directive 반복)가 된다.
  - THE SYSTEM SHALL F1의 Stop 차단(directive 발화) 조건을 **`pending`만으로 판정**한다(`pending ≥ 1`일 때만 차단). `unmapped ≥ 1`은 directive 반복 대상이 아니며, F16의 1회성 안내 메시지 경로로 처리한다(반복 스팸 없음).
- Acceptance: 매핑표에 없는 가상 repo 경로(예: `pptx-template/Docs/sdd guide/`)를 입력한 fixture에서 raw 파일이 생성되지 않고 경고 리스트에 해당 경로가 포함됨을 검증하는 pytest가 존재한다. `unmapped ≥ 1`이고 `pending == 0`인 상태를 fixture로 구성했을 때 F1의 Stop 훅이 차단하지 않고(`{"continue": true}`) `unmapped` 안내만 1회 출력됨을 검증하는 테스트가 존재한다.

### F13: 결정적 코어 — Python stdlib-only 패키지
- THE SYSTEM SHALL 스캔·해시 dedup·네이밍 변환·멱등 판정·카운트 검증 로직을 `hooks/lib/` 아래 신규 Python 패키지(예: `hooks/lib/kompound_snapshot/`)에 구현한다.
- THE SYSTEM SHALL 이 패키지가 표준 라이브러리만 사용하고(외부 pip 의존 없음), 네트워크 호출과 LLM 호출을 하지 않도록 구현한다.
- WHERE 예상치 못한 예외가 발생할 때 THE SYSTEM SHALL 프로세스를 비정상 크래시시키지 않고 F11의 "스캔 실패" 신호로 변환해 반환한다(fail-safe).
- Acceptance: `hooks/lib/kompound_snapshot/` 내 모든 `.py` 파일에 대해 `import` 문에 stdlib 외 모듈(예: `requests`, `openai` 등)이 없음을 정적 검사하는 테스트가 `tests/`에 존재하고 통과한다. 이 패키지에 대응하는 `tests/test_kompound_snapshot_*.py`가 `PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q`로 실행 가능하다.
- **오프라인 테스트용 fixture 구조** — 실제 kompound·네트워크 없이 F1~F16 전 경로를 검증하려면, pytest fixture가 임시 디렉토리(`tmp_path`) 아래 다음 구조를 만들고 F16의 주입 경로(스캔 루트·kompound 저장소)로 지정해야 한다:
  ```
  <tmp>/fake_kompound/
    raw/
    wiki/sdd-spec-registry.md
    wiki/index.md
    wiki/log.md
  <tmp>/fake_workspace/
    <repo>/docs/sdd/spec/...
    <repo>/docs/sdd/design/arch/...
    <repo>/docs/sdd/result/...
    <repo>/worktrees/<wt>/docs/sdd/spec/...   (워크트리 전용 문서 케이스)
  ```
  `fake_kompound`를 git 저장소로 초기화(`git init` + 초기 커밋)해 F9(dirty/diverge)·F8(검증 게이트) 케이스도 동일 fixture 위에서 시뮬레이션 가능해야 한다. 이 구조를 생성하는 공용 fixture 함수(예: `tests/conftest.py`의 `fake_kompound_env`)가 존재하고, F3·F5·F6·F7·F8·F9·F11·F12·F16 테스트가 이를 재사용함을 확인한다(중복 fixture 정의 없음).

### F14: T2 게이트 — 기존 패턴 준수 등록
- THE SYSTEM SHALL T2 게이트 스크립트를 `hooks/enforcement/` 아래에 위치시키고, `hooks/enforcement/worktree-add-gate.sh`와 동일한 라이브러리 소싱 패턴(`lib/constants.sh`, `lib/logging.sh` 등)을 사용한다.
- THE SYSTEM SHALL `hooks/hooks.json`의 `PreToolUse`/`matcher: "Bash"` 훅 배열에 신규 게이트 커맨드를 `${CLAUDE_PLUGIN_ROOT}/hooks/enforcement/<신규스크립트>.sh` 형식으로 추가한다.
- Acceptance: `hooks/hooks.json`이 유효한 JSON이고, `PreToolUse` > `matcher:"Bash"` 배열에 신규 게이트 커맨드 항목이 정확히 1개 추가되어 있으며, 기존 5개 항목(`dangerous-command.sh`, `secret-detect.sh`, `branch-gate.sh`, `worktree-add-gate.sh`, `e2e-gate.sh`)이 그대로 보존됨을 검증한다.

### F15: 2티어 판정 — 하네스 티어, 사람 승인 필요
- THE SYSTEM SHALL 이 feature 전체(신규 게이트 스크립트, `hooks/hooks.json` 수정, `skills/sdd-orchestrator/SKILL.md` 프롬프트 수정, `hooks/lib/` 신규 패키지)를 "하네스 티어" 변경으로 분류한다.
- WHERE 변경 대상이 게이트 스크립트 신규 생성을 포함할 때 THE SYSTEM SHALL CLAUDE.md의 protected set 규칙(게이트 스크립트는 자동 생성/수정 금지, 사람만 가능)에 따라 사람 승인 없이는 최종 머지를 진행하지 않는다.
- Acceptance: result 문서(Phase 4 완료 시)에 "이 사이클은 사용자가 이번 대화에서 명시적으로 지시하여 protected-set 승인 조건을 충족했다"는 문장이 기록되어야 한다. PR 설명에 "하네스 티어 / 사람 승인 완료" 표기가 있어야 머지 가능.

### F16: 환경 설정 주입 — 스캔 루트 · kompound 저장소 · 프리픽스 매핑 [BLOCKER 대응]

moon-harness는 범용 Claude Code 플러그인이다(CLAUDE.md "레포 특화 하드코딩 금지"). F1~F15에서 다루는 스캔 루트, kompound 저장소 경로, 프리픽스 매핑 10종은 현재 사용자(moon) 환경 고유의 값이며, 구현에 리터럴로 박아 넣어서는 안 된다.

- THE SYSTEM SHALL 스캔 루트 경로와 kompound 저장소 경로를 다음 순서로 해석한다: ① 환경변수 → ② 하네스 설정 파일 → ③ 자동 탐색 → ④ 미설정.
- 환경변수/설정 키의 구체 이름과 설정 파일의 위치는 이 spec에서 확정하지 않는다 — Phase 2(architect)의 결정 사항이다. spec은 "주입 가능해야 하고 위 순서로 해석되며 단일 진실 지점(single point of resolution)에서 처리된다"까지만 요구한다.
- IF 위 4단계 어디에서도 kompound 저장소 경로가 해석되지 않으면 THEN THE SYSTEM SHALL 이를 오류로 취급하지 않고 박제 기능을 **비활성화**한다 — 실행당(또는 세션당) 1회만 안내 메시지를 남기고, SDD 사이클 완료 처리(T1)와 Bash 명령(T2)을 정상 통과시킨다.
  - 근거: 범용 플러그인이 kompound를 쓰지 않는 사용자의 SDD 사이클이나 `git worktree remove`를 막아서는 안 된다(CLAUDE.md fail-safe 원칙). 이 규칙은 T1(F1)·T2(F2) 양쪽에 동일하게 적용된다.
- THE SYSTEM SHALL 프리픽스 매핑표(F4)를 코드 리터럴이 아닌 **설정 데이터**로 보유하며, F4에 열거된 10종을 기본값으로 제공한다. 매핑에 없는 repo는 기존 F12(경고만, 박제 안 함) 경로를 그대로 따르며, 그 문서는 F12의 `unmapped` 카운터로만 집계된다(`pending`에는 합산하지 않는다 — F12 참조). kompound 경로 미설정 시의 "1회 안내"(이 절)와 프리픽스 미등록 시의 "1회 안내"(F12의 `unmapped` 경로)는 서로 독립된 별개의 안내이며 조건을 합치지 않는다.
- Acceptance:
  - `hooks/lib/kompound_snapshot/` 아래 어떤 `.py` 파일에도 스캔 루트·kompound 저장소를 가리키는 사용자 고유 절대경로 리터럴(예: `/Users/<user>/...` 패턴)이 존재하지 않음을 정적 검사하는 테스트가 `tests/`에 존재하고 통과한다(리터럴 카운트 0).
  - 경로·매핑 해석이 단일 함수(예: `resolve_config()`)로 캡슐화되어 있고, 그 함수를 테스트에서 임의의 스캔 루트/kompound 경로/프리픽스 매핑으로 오버라이드해 F3~F14 전 파이프라인을 실행할 수 있음을 검증하는 테스트가 존재한다.
  - kompound 저장소 경로가 해석되지 않는 환경을 시뮬레이션했을 때 T1이 "무동작 통과"(F1 Acceptance)로, T2가 `gate_pass`(F2 Acceptance)로 각각 종료됨을 검증하는 테스트가 존재한다.
  - 동일 실행 내에서 미설정 안내 메시지가 정확히 1회만 출력됨(반복 스팸 없음)을 검증하는 테스트가 존재한다.
  - 프리픽스 매핑이 기본 10종과 다른 커스텀 매핑(예: 11번째 repo 추가)으로 주입됐을 때 F4 네이밍 로직이 그 커스텀 매핑을 그대로 사용함을 검증하는 테스트가 존재한다.

### F17: 회귀 안전망 — stop-pipeline.py / hooks.json 수정 전 characterization test 선행

**배경 (실측, 2026-07-29)**: `PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q` → 533 passed. 그러나 `hooks/enforcement/stop-pipeline.py`(약 450줄, protected set)에 대한 **행위 테스트는 0개**다. `tests/test_protected_guard.py:42`, `tests/test_tier_classifier.py:32`의 참조는 protected 경로 문자열 목록일 뿐 동작 검증이 아니다. D2에 따라 F1(T1 강제)이 이 파일에 신규 라벨 분기와 "박제 미완이면 전진 금지" 로직을 추가해야 하므로, **무테스트 상태의 protected 파이프라인 제어 핵심부를 수정하는 것**이 이 feature의 최대 리스크다.

- WHEN `hooks/enforcement/stop-pipeline.py` 또는 `hooks/hooks.json`을 수정하는 태스크를 시작하기 전에 THE SYSTEM SHALL 해당 파일의 **현재 동작을 고정하는 회귀 안전망 테스트**가 `tests/` 아래에 존재하고 전부 GREEN임을 먼저 확인한다.
- IF 회귀 안전망이 GREEN이 아니면 THEN THE SYSTEM SHALL stop-pipeline.py / hooks.json 수정 태스크를 시작하지 않는다.

**안전망 스코프 (좁게 — 리드 결정, 아래 5개가 전부다)**:
  1. `decide()`(L334)의 라벨 전이 결과 — 입력 라벨·상태 → 반환 directive/전진 여부
  2. `DIRECTIVES` 테이블(L63) 선택 로직 — 라벨 → directive 매핑
  3. `label_prerequisite_met()`(L296)의 선행조건 판정
  4. 라벨 추가로 영향받는 서킷브레이커 카운팅 — `check_circuit_breaker`(L262) / `increment_breaker`(L279) / `reset_breaker`(L286)
  5. `hooks/hooks.json` 유효성 — 게이트 등록 후에도 JSON 파싱 성공 + **기존 훅 엔트리가 전부 보존**됨

스코프 외(`is_stale`(L230) staleness, `check_session_match`(L253) 세션 매칭, `atomic_write`(L209) 등)는 **이번 사이클의 안전망 대상이 아니다**. 전체 커버리지를 목표로 하면 사이클이 그쪽으로 끌려간다 — 이 feature가 실제로 건드리는 경로만 고정한다.

**성격 (중요)**: 이 안전망은 **characterization test**다 — 현재 동작을 정답으로 고정하므로 현재 존재하는 버그까지 함께 박는다. THE SYSTEM SHALL 이 테스트 파일을 스펙(정답의 근거)으로 취급하지 않으며, 어떤 현재 동작이 잘못이라고 판단되면 안전망을 **의도적으로 갱신**하는 절차를 따른다(테스트를 통과시키려 구현을 왜곡하지 않는다).

**실행 주체**: `sdd-test-automator`의 **refactor 모드**(회귀 안전망)가 담당한다. tdd 모드(신규 기능 RED)와 구분한다 — 신규 파일(F13 Python 코어, F2 게이트 스크립트)은 기존대로 tdd 모드 RED→GREEN이고, F17은 **기존 파일 수정 전** 안전망이다.

**배치 (Phase 3 힌트)**: 이 안전망 작성은 Phase 3에서 **Wave 0 선행 태스크**로 배치되어, 안전망 GREEN 확인 후에야 stop-pipeline.py·hooks.json 수정 태스크(F1·F14)가 시작되도록 의존 관계를 갖는다. 구체 태스크 분해는 taskmaster 몫이다.

- Acceptance:
  - `tests/` 아래에 stop-pipeline.py의 위 4개 경로(`decide`/`DIRECTIVES`/`label_prerequisite_met`/서킷브레이커)를 커버하는 테스트 파일이 존재하고, **stop-pipeline.py를 수정하기 전 시점의 코드에 대해** 전부 GREEN이다.
  - `hooks/hooks.json` 유효성 테스트가 존재하며, 게이트 등록 전/후 모두에서 JSON 파싱 성공 및 기존 엔트리 보존을 검증한다.
  - 안전망 테스트 파일 상단에 "characterization test — 현재 동작 고정, 스펙 아님" 취지의 주석이 있다.
  - 안전망 스코프 외 항목(staleness·세션 매칭·atomic_write 등)이 이번 사이클 대상이 아님이 문서화되어 있다.
  - 전체 스위트가 계속 GREEN이다(기준: 이 사이클 시작 시점 533 passed — 신규 테스트 추가로 총수는 증가하되 **기존 533개 중 실패 0**).

## 용어 정의

- **박제(snapshot)**: SDD 사이클이 만든 spec/arch/ui/api/context/result 문서를 `marvelous_kompound/raw/`에 원문 그대로(verbatim) 복사하는 행위. 변형 없음.
- **kind**: 문서의 산출물 종류. `spec` `arch` `ui` `api` `context` `result` 6종(`development/` 디렉토리는 `arch`로 매핑).
- **canonical**: 동일 내용(md5 동일)이 여러 경로에 중복 존재할 때, dedup 규칙(non-worktree 우선 → 경로 짧은 것 우선)으로 선택된 대표 경로.
- **drift**: 이미 박제된 raw와 home repo의 현재 living 문서 내용이 달라진 상태. 이 훅이 다루는 주 실패 모드는 아니다("낡음"이 아니라 "빠짐"이 문제).
- **워크트리(worktree)**: `git worktree`로 생성된 SDD 작업 사본(`*/worktrees/*` 경로). 삭제 시 그 안의 문서도 함께 사라진다.
- **registry**: `wiki/sdd-spec-registry.md`. raw로 박제된 SDD 문서를 프로젝트/feature별로 정리한 파생 카탈로그.
- **프리픽스 매핑**: home repo 이름 → kompound raw 파일명 접두어(`<project>`) 대응표. F4가 기본 10종을 정의하고, F16에 따라 코드가 아닌 설정 데이터로 보유되어 교체·확장 가능하다.

## 범위 밖

- 주제별 위키 페이지(`loop-engineering.md` 등) 합성 — 사람이 `/ingest`로 판단해 갱신. 이 훅은 건드리지 않는다.
- `docs/sdd/task/` `tasks/` 하위 태스크 문서 박제 — 기계적·고churn이라 코드/git이 더 정확한 소스.
- home repo(`Marvelous`, `moon-harness` 등) 쪽 문서를 kompound 내용으로 역방향 수정 — 훅은 kompound에만 쓰는 단방향 흐름이다.
- 과거(이 훅 도입 이전) feature의 result 결손 소급 백필 — registry의 기존 결정(2026-07-28)대로 결손은 결손인 채로 둔다.

## 결정 기록 — 설계 SSOT가 열어둔 항목의 확정 (2026-07-29, 사용자)

설계 SSOT에 없거나 옵션만 제시된 4개 항목을 Phase 1에서 확정했다. 아래 결정은 해당 F 요구사항 본문에 이미 반영되어 있다.

| # | 항목 | 결정 | 근거 | 반영 |
|---|------|------|------|------|
| D1 | **T1 삽입 지점** — 설계 SSOT L46-52는 "self-improve 호출부 옆"(= 현행 Step 5)을 지정하지만, `skills/sdd-orchestrator/SKILL.md:170`의 Step 4-5(worktree 정리)가 Step 5보다 앞이라 "워크트리가 아직 살아 있다"는 전제(L50)를 위반한다 | **Step 4-2(`ORCHESTRATOR_STATE.md` = COMPLETED) 직후**, 4-3(push+pr-converge) 이전 | 사용자: "4-3은 대부분 의도를 바꾸는 게 아니라 코드단의 수정이야. 보통 4-2가 끝나면 의도가 잘못되어서 수정하는 경우는 없어." → 박제 대상 문서의 의도가 4-2에서 확정된다. 설계 전제 3개(result 이후·워크트리 생존·self-improve보다 먼저)를 모두 만족 | F1 |
| D2 | **T1 강제 수준** — 설계 SSOT는 트리거가 프롬프트 지시인지 코드 강제인지 명시하지 않음 | **`hooks/enforcement/stop-pipeline.py`의 라벨 directive로 결정적 강제** (프롬프트 지시만으로 두지 않음) | 이 feature의 동기가 "사람/에이전트의 성실성에 의존하지 않는다"이므로 산문 지시는 동기와 상충. T1·T2를 모두 결정적으로 강제해 이중화 | F1 |
| D3 | **T2 차단 정책** — 설계 SSOT L64-65는 "차단이 과하면 완화 가능, 단 조용한 통과는 금지"까지만 정함 | **자동 박제 시도 → 성공 시 경고 후 통과 / 실패 시에만 `exit 2` 차단**<br>**→ D5로 차단 범위 축소됨(아래 참조)** | T2가 막는 것은 "박제 실패"가 아니라 "미시도 문서의 존재". 실패 원인은 소수지만 실재(F9 dirty는 2026-07-28 실측·F12 미등록 프리픽스) → 그 경우만 차단하면 "조용한 통과 금지"를 지키면서 정상 흐름을 끊지 않는다 | F2 |
| D5 | **T2 차단 범위** — D3은 "박제 시도 실패"를 단일 사건으로 보고 차단했다. arch 리뷰가 이것이 C-1과 동일한 함정임을 지적했다: registry 파싱이나 검증 게이트가 어긋나면 **우리가 만들지 않은 카탈로그 결함으로 워크트리 삭제가 계속 막힌다** | **`apply`를 (i) raw 복사 / (ii) 카탈로그 갱신 2단으로 분리하고, T2 차단은 (i) 실패만.** (ii) 실패(F8 게이트 · `catalog_unparsed`)는 경고 후 통과. kompound 경로 부재도 통과(F16 `disabled`) | 사용자 선택(2026-07-29). registry 파싱 실패는 "박제 대상 문서가 위험하다"가 아니라 "카탈로그 갱신 방법을 모른다"다. **T2의 목적은 "워크트리를 지워도 문서가 kompound에 남아 있는가"이며 raw 복사가 성공했다면 이미 달성됐다.** 대가는 "카탈로그가 한 사이클 뒤처짐"으로, "사용자가 워크트리에 갇힘"보다 작다 | F2, F7, F8 |
| D4 | **T2 미박제 판정 방식** — 설계 SSOT에 구체화 없음 | **F13 Python 결정적 코어를 서브프로세스로 호출**(부작용 없는 `--check` 확인 모드). bash에 스캔·네이밍·dedup 로직 중복 구현 금지 | CLAUDE.md 결정↔판단 분리 원칙 + 단일 구현 유지(두 곳에 규칙이 갈라지면 T1/T2 판정이 어긋난다) | F2, F13 |

### 현재 환경 기준값 (참고용 — 코드에 리터럴로 넣지 않는다)

F16에 따라 스캔 루트·kompound 저장소 경로·프리픽스 매핑은 모두 주입 대상이다. 아래는 F1~F15 본문 작성 시 근거로 삼은 **현재(moon) 환경의 실제 값**이며, F16의 해석 순서(환경변수 → 설정 파일 → 자동 탐색) 중 어느 한 단계의 결과로 채워질 기본값 후보다. 구현체는 이 표의 값을 코드 리터럴로 박아 넣지 않는다.

| 항목 | 현재 값 | 비고 |
|---|---|---|
| 스캔 루트 | `/Users/moon/workspace` | F3이 참조하던 절대경로. F16 이후 "주입된 스캔 루트"로 본문 수정됨 |
| kompound 저장소 | `/Users/moon/workspace/marvelous_kompound` | F7·F8·F9가 참조하던 kompound 워킹트리 경로 |
| 프리픽스 매핑(기본 10종) | `Marvelous`/`Marvelous_dev`/`Marvelous_feature`/`Marvelous_code_review`/`auto-fix-base`→`marvelous` · `CLOFab_Web`(`clofab/` 포함)→`clofab` · `Marvelous_graphify`→`graphify` · `auto-fix-orchestrator`→`autofix` · `crash-ai-analysis`→`crashai` · `codegraph-clo`→`codegraph` · `ai-code-reviewer-action`→`aireview` · `moon-harness`→`harness` · `rein`→`rein` · `claude-slack-channel`→`slack` | F4 본문에 "기본 매핑"으로 남아있는 것과 동일한 데이터. F16에 따라 설정으로 교체·확장 가능 |

## 미결정 / 사용자 확인 필요

없음 — 위 D1~D4로 전부 해소되었다.

---

## Blocker Check — Phase 1 검사 결과 (2026-07-29 2차)

**Status:** PASS

**검사 항목 (완료)**:
1. 플랫폼/스택 확정 ✓
2. EARS 표기 준수 ✓
3. Acceptance 기계 검증 가능성 ✓
4. 요구사항 간 모순 검증 ✓
   - F1 protected set vs F15 (충돌 무, 사람 승인 명시)
   - F2↔F9 순서 (1차 WARN → 명시됨)
   - F6↔F11 멱등성 (일관성 확인)
   - F7↔F8 0건 조건 (1차 WARN → 명시됨)
   - F16 "미설정 시 비활성화" vs 소실 방어 동기 (fail-safe 원칙 인지)
5. F16 신규 요구사항 모순 검증 ✓
   - 환경변수 → 설정파일 → 자동탐색 → 미설정 해석 순서
   - 미설정 시 1회 안내 + 기능 비활성화 (조용한 0건 금지 준수)
   - 구체 키 이름 위임 (정당한 범위)
6. 누락된 블로커 (경로 하드코딩) 1차 BLOCKER 해소 ✓
   - 스캔 루트 / kompound 저장소 / 프리픽스 매핑 주입화
   - 현재 환경 기준값 격리 (코드 리터럴 금지)
7. 테스트 가능성 ✓
   - 오프라인 fixture 구조 명시 (fake_kompound, fake_workspace)

**잔여 WARN 사항**: 없음

**다음 단계**: Phase 2(architect) — F16의 구체 환경변수명·설정파일 위치 결정 가능

---

## Blocker Check — Phase 1 검사 결과 (2026-07-29 3차, F17 추가 대응)

**Status:** PASS

**F17 추가에 대한 3차 재검사 항목**:
1. F17 내용 확인 ✓ — 회귀 안전망(characterization test), 스코프 5개, Wave 0 배치, F1과 연동
2. F17 → F1 순환 의존 검증 ✓ — 선형 순서 (F17 기존 코드 → 안전망 Green 확인 → F1 수정), 데드락 없음
3. F17 자기참조 검증 ✓ — "안전망 작성 태스크"는 "수정 태스크" 제약 대상 외
4. "533개 중 실패 0" 기준 검증 ✓ — baseline 비교로 기계 검증 가능, 총수 증가는 명시적 허용
5. characterization test vs Acceptance 구분 ✓ — "스펙 아님" 명시, 정답 검증(F8/F13)과 현재 동작 고정(F17) 구분
6. Wave 0 배치가 taskmaster DAG 권한과 충돌 ✓ — 순서 제약만 요구, 구체 분해는 위임
7. F15(protected set) vs F17 관계 ✓ — 직교적 (F17 = 선행조건, F15 = 승인조건, 미변경)
8. 1·2차 항목 회귀 ✓ — EARS / Acceptance 기계 검증 / 경로 하드코딩 / F2↔F9 / F6↔F11 / F7↔F8 / F16 모두 유지

**결론**:
- F17의 안전망은 F1(stop-pipeline.py 수정) 시작의 필요조건이지만 충분조건 아님
- F15의 사람 승인 요건은 F17의 안전망으로 대체되지 않음 (여전히 필수)
- 순환 의존, 자기참조, 데드락 없음
- Acceptance 모두 검증 가능

**잔여 WARN 사항**: 없음

**다음 단계**: Phase 3(taskmaster) — F17 Wave 0 배치 + F1·F14 의존 관계 구성 가능

---

**arch 리뷰 반영(2026-07-29): S-1~S-6 — 재검사 필요**

**arch 리뷰 2차 반영(2026-07-29): S-7~S-10**

**arch 리뷰 3차 반영(2026-07-29): S-11~S-14 (A-5 · ③ 전파)**
