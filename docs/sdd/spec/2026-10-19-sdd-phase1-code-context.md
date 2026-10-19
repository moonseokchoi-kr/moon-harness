# SDD 단일 문서 파이프라인 (Phase 1~3 재구성)

## 목표

- 무엇을: SDD Phase 1~3을 "spec 한 문서" 중심으로 재구성한다.
  - Phase 1: `sdd-ux-researcher` 단계를 없애고 인터뷰 단계로 바꾼다. sdd 리드가 `grill`로 사용자와 인터뷰하고, 사실이 필요하면 `why` / `code-mapper`를 `subagent_type: Explore`로 보내 조사한다. 명시적 yes 뒤에 `sdd-spec-writer`가 새 단일 문서 골격으로 spec을 쓴다.
  - Phase 2: 조건부 아키텍처 자리. spec 설계 결정에 아키텍처 변경 필요가 적혔을 때만 architect가 같은 문서를 보강한다.
  - Phase 3: worktree 생성을 여기로 옮기고, taskmaster가 같은 문서에 "구현 계획"을 쓴 뒤 task 문서와 DAG를 만든다. 사용자 승인은 Phase 1 spec, Phase 3 plan+tasks 2회다.
- 왜: 이 하네스의 주 사용처는 제로베이스가 아니라 기존 코드 수정이다. 그런 작업에서는 페르소나/여정보다 "현재 코드에서 구현을 막는 것"과 "기존에 왜 그렇게 작성되었는가"가 근거로 쓸모 있다. 또 spec/arch/ui/api/context 5종 문서는 서로 어긋나기 쉽고 승인 게이트만 늘린다.
- 성공의 모습:
  1. Phase 1이 grill 인터뷰 → 명시적 yes → spec 작성 순서로 돌고, 사용자는 환경에서 알 수 있는 사실을 질문받지 않는다.
  2. 새 SDD 사이클은 `docs/sdd/spec/{date}-{feature}.md` 한 문서 + task 문서 + `ORCHESTRATOR_STATE.md`만 만든다. `docs/sdd/design/`, `docs/sdd/context/`는 새로 만들어지지 않는다.
  3. 구 라벨이 저장된 진행 중 `pipeline.json`이 깨지지 않는다.
  4. 삭제된 에이전트 4종(`sdd-ui-designer`, `sdd-api-designer`, `sdd-architect-reviewer`, `sdd-context-manager`)과 `sdd-ux-researcher`에 대한 참조가 `docs/sdd/**` 밖에 0건이다.
  5. 오프라인 `tests/` 전체가 통과하고 `skills/sdd/SKILL.md` 줄 수 ≤ 671(현재 671줄)이다.
- 진행 방식: 한 사이클, 회귀 격리는 Wave 순서. Wave 1 = Phase 1(F1~F8), Wave 2 = Phase 2·3과 공통(F9~F15). 각 Wave 끝에서 오프라인 pytest가 통과해야 다음 Wave로 간다.

배경(범위 밖): idea-workshop 제거는 `b3a7ff8`로 완료됐다.

## 사용자 요구사항 (원문)

| # | 사용자 요구 | → 기능 |
|---|------------|--------|
| 1 | "ideaworkshop은 딱히 필요없는것 같아 오히려 방해되더라고, 제로베이스에서 만드는게 아니다보니가 idea workshop이 필요없더라고, grilling이나 interview-me정도만 있어도 충분할것 같아" | F2, F4 (idea-workshop 제거 자체는 b3a7ff8로 완료, 범위 밖) |
| 2 | "ux-researcher 단계도 필요없을것 같아 이부분은 오히려 pstack의 /how, /why가 들어가서 우리의 요구사항에 대해 현재 코드에서 구현을 할때 무엇이 걸림돌이 되는지 기존에 왜 그렇게 작성되었는지를 판단하는게 더 좋아보여" | F1, F3, F4, F5, F6, F7 |
| 3 | 선택: "why 신설 + how는 code-mapper 확장" / 인터뷰는 "독립 스킬 + sdd 연동" | F1, F2, F3, F4 |
| 4 | (원문 아님) 2026-10-19 sdd 리드가 전달한 "범위 확장 확정 결정" 요약: Phase 1~3 단일 문서 재구성, Phase 2 조건부 아키텍처, worktree Phase 3 이동, FULL/SIMPLE 폐지, 빌드 프로파일 Phase 4 진입 시 확보, E2E 설계 단계 제거, 에이전트 4종 삭제, 0.15.0. 사용자 원문 인용이 아니라 확정 결정의 요약이다. | F5~F15 |

## 가정

- A1. 인터뷰 단계는 대화형 세션에서만 돈다. `/loop`, 스케줄, CI 같은 비대화형 실행은 grill을 시작하지 않고 Phase 1을 멈춘 채 사용자 입력이 필요하다고 보고한다.
- A2. 서브에이전트(why, code-mapper)는 사용자와 대화할 수 없다. 사용자와의 대화는 sdd 리드만 한다.
- A3. `skills/sdd/SKILL.md` 줄 수 기준선은 리드 실측 671줄이다. 상한은 "≤ 671"이다. spec 템플릿 본문은 `skills/sdd/references/spec-template.md`로 분리한다.
- A4. 사용자 yes 판정은 sdd 리드의 판단(프롬프트)이다. 결정적 코드로 판정하지 않는다.
- A5. `build-notes`는 사용자 전역 스킬이라 플러그인 밖에 있고, 어떤 사용자 환경에는 없을 수 있다. 그래서 반드시 폴백이 있어야 한다.
- A6. 릴리즈 버전은 0.14.0 → 0.15.0(새 스킬 추가, minor)이다.
- 용어: frontier = 선행 결정이 모두 확정되어 추측 없이 지금 물을 수 있는 질문 집합. 코드 앵커 = 조사 출발점(파일/라인, 심볼, 커밋, PR 번호). 별칭 라벨 = 구 `pipeline.json` 호환을 위해 `DIRECTIVES`에 남긴 구 라벨 키.

## 코드 조사

범위: 이번 확장 범위의 파일을 직접 읽었다. 사실 / 추론 / 모름을 구분한다. 도입 이력은 sdd 리드 실측으로 확보했다(H38).

### how — 구현 걸림돌

확인된 사실 (stop-pipeline.py, `hooks/enforcement/stop-pipeline.py`):

- H1. `DIRECTIVES`(85-196행)에 라벨 18개 + 터미널 `PHASE4_WORKTREE_CREATED: None` + kompound 전용 `PHASE4_KOMPOUND_SNAPSHOT_PENDING`이 있다. 현재 체인은 PHASE1 4개(`PHASE1_UX_RESEARCH_DONE`, `PHASE1_SPEC_DRAFT`, `PHASE1_BLOCKER_CHECK_PASS`, `PHASE1_USER_APPROVED`), PHASE2 8개(`PHASE2_START`, `PHASE2_WORKTREE_CREATED`, `PHASE2_ARCH_STRUCTURE_DONE`, `PHASE2_ARCH_USER_APPROVED`, `PHASE2_UI_DESIGN_COMPLETE`, `PHASE2_API_DESIGN_COMPLETE`, `PHASE2_DESIGN_USER_APPROVED`, `PHASE2_USER_APPROVED`), PHASE3 4개(`PHASE3_PLAN_START`, `PHASE3_TASKMASTER_DONE`, `PHASE3_DAG_CONSTRUCTED`, `PHASE3_USER_APPROVED`)다. 요청문은 PHASE2 "9개"라고 했으나 실측은 8개이고, 리드 실측으로 8개 전부가 별칭 대상임이 확정됐다(D7).
- H2. 삭제 대상 에이전트를 directive가 직접 호출한다: `PHASE1_UX_RESEARCH_DONE`(86-91행)→`sdd-ux-researcher`, `PHASE2_WORKTREE_CREATED`(115-122행)→`sdd-architect-reviewer`, `PHASE2_ARCH_USER_APPROVED`(129-134행)→`sdd-ui-designer` + `e2e-config.json` 생성 + FULL/SIMPLE 분기, `PHASE2_UI_DESIGN_COMPLETE`→Stitch/ui 승인, `PHASE2_API_DESIGN_COMPLETE`→`sdd-api-designer`, `PHASE2_DESIGN_USER_APPROVED`(147-151행)→`sdd-context-manager`. 즉 별칭 directive는 구 문구를 그대로 둘 수 없다(삭제된 에이전트 참조 0건 Acceptance와 충돌).
- H3. `PHASE2_START`(110-114행) directive가 worktree 생성(`Skill(git-worktree)` + `worktree_path` 기록)을 지시한다. 이 책임이 Phase 3으로 이동한다.
- H4. `label_prerequisite_met`(333-366행)의 `checks`(344-356행)는 파일 존재 기반이다: `has_spec`(`docs/sdd/spec/*.md` 아무 파일), `has_blocker_pass`, `has_worktree`, `has_arch`(`design/arch/*.md`), `has_ui`, `has_api`, `has_context`, `has_tasks`, `has_orchestrator_state`. `PHASE2_USER_APPROVED`만 `state.get("mode") == "FULL"`일 때 `has_context`를 요구한다(351-353행). 검증 예외는 fail-safe로 `(True, "")`.
- H5. `decide()`(578-649행)의 Step 4 서킷 브레이커(`CB_MAX_BLOCKS = 20`, TTL 5분), Step 5 터미널 라벨, Step 6 `waiting_for_user`면 멈춤 허용(627-629행), Step 8 `DIRECTIVES.get(label)`이 없으면 `continue: True`(634-637행, 미지 라벨 분기). 따라서 별칭 없이 구 라벨 키를 지우면 진행 중 pipeline은 조용히 풀린다.
- H6. 인터뷰 대기 충돌: 라벨이 `PHASE1_INTERVIEW_START`인 채 `waiting_for_user=false`이면 Claude가 사용자 응답을 기다리려 멈출 때마다 Stop 훅이 block + directive를 재주입한다(Step 6 우회 필요). 기존 `waiting_for_user` 메커니즘으로 해소 가능하다.
- H7. `waiting_for_approval_type`은 `pipeline-utils.sh`(62, 92, 108, 151행)가 저장·표시만 하고 `stop-pipeline.py`는 값으로 분기하지 않는다(directive 문자열 안에서만 등장). 따라서 `'interview'` 값은 안전하다(리드 확인과 일치, grep 재확인 완료).

확인된 사실 (pipeline-utils.sh, `hooks/enforcement/lib/pipeline-utils.sh`):

- H8. `init_pipeline <feature> <mode:FULL|SIMPLE>`(33-36행)가 `mode`(기본 SIMPLE)를 `pipeline.json`에 쓰고(57행) 완료 메시지에 출력한다(76행). 초기 라벨은 `PHASE1_UX_RESEARCH_DONE` 하드코딩(60행). `show_pipeline`이 `mode`를 출력한다(149행). 사용 주석에 `init_pipeline "modal-system" "FULL"`(7행)과 `advance_label "PHASE2_ARCH_STRUCTURE_DONE"`(9행)이 있다. `mode`를 읽는 코드는 `stop-pipeline.py:352` 하나뿐이다.
- H9. 상태 디렉터리는 `CLAUDE_PROJECT_DIR`로 정해진다(`lib/constants.sh` 6, 20행). 따라서 임시 디렉터리 + 환경변수로 `init_pipeline`을 오프라인 테스트할 수 있다.

확인된 사실 (게이트 훅):

- H10. `hooks/enforcement/e2e-gate.sh`: `e2e-config.json`이 없거나 `enabled`가 true가 아니면 즉시 통과(29-31행). 기본 `e2e-config.json`(`enabled: false`)은 `hooks/enforcement/lib/init-state.sh` 36-50행이 생성한다. `sdd-ui-designer`(40, 61-94행)는 `enabled` 설정을 쓰는 쪽이며, 설계 단계에서 `enabled` 설정을 만들지 않으면 이 훅은 휴면이다. 수정 불필요.
- H11. `hooks/enforcement/phase-gate.sh`(SessionStart, 경고만): Phase 2 판정을 `docs/sdd/design/arch*`(49-55행)로, E2E 경고를 `design/ui` 존재(94행)로 한다. 새 흐름은 `design/`을 만들지 않으므로 Phase 2 판정과 E2E 경고는 발화하지 않는다. 또 `case`에서 `"2_done"|"3_done"` 분기(73행)가 `"3_done"` 단독 분기(79행)보다 앞서 있어 79행 분기는 원래 도달 불가다(사실로 기록, 선재 결함). 경고만 하는 훅이지만 Phase 2 design 판정(`DESIGN_DIR`, `HAS_ARCH/UI/API`, `2_done`)과 "Phase 3 태스크가 있지만 Phase 2 architecture 설계 문서가 없습니다" 경고, UI 명세/e2e-config 경고(약 96-104행)가 새 흐름에서 오경고를 낼 수 있고 `CONTEXT_DIR`에도 의존하므로 수정 대상이다(F14, B3). `case` 분기 순서 결함 자체는 이번에 고치지 않는다.
- H12. `[TDD == FULL]`(엔지니어 에이전트 11종 + `sdd-implementer`), `tdd-gate.sh:64`, `state-reader.sh:29`("FULL or SKIP"), `sdd-taskrunner/assets/prompts/analyze.md:19`, `skills/sdd/HANDOFF.md`의 FULL은 **TDD 모드**이며 설계 모드 FULL/SIMPLE과 무관하다. 일괄 치환하면 안 된다.

확인된 사실 (skills/sdd/SKILL.md, 671줄):

- H13. 설계 모드 FULL/SIMPLE 지점: 시작(24-28행), 흐름(35행), 하위호환(671행), Phase 판정 표(146행), Phase 2 모드 판정(300-306행), SIMPLE 모드(319-323행), FULL 모드(325-359행), Phase 3 진입 검증 3-4행(479-480행), 게이트 정책(593-594행). 87행 "FULL 태스크"는 TDD 용어다.
- H14. 문서 구조(112-131행)가 `design/{arch,ui,api}`, `context/`, `e2e-config.json`(129행)을 정의한다. "정밀 모드: context 문서의 `## 라벨 상태`"(137행)는 `sdd-context-manager`가 쓰는 문서에 의존한다.
- H15. 에이전트 표(197-225행)에 5개 삭제/개명 대상이 있다(199, 200, 202, 206, 207행). Phase 1(229-263행) 프로세스는 ux-researcher 1단계 + 템플릿. 상태머신은 160-165행.
- H16. 자연어 승인 표(44-52행)가 "좋아", "ok" 등을 승인으로 처리한다. grill의 "명시적 yes만" 규칙과 충돌한다.
- H17. "모든 레이어에 테스트" 표(361-374행)에서 View/UI 행(369행)과 373행 주석이 E2E를 필수로 강제한다. 아키텍처 문서 템플릿(376-421행)과 빌드 프로파일 발견 절(436-442행)은 architect의 책임으로 적혀 있다.
- H18. Phase 4 진입 검증 5번(535행): "`ORCHESTRATOR_STATE.md`에 빌드 프로파일 메타 존재 / 없으면 Phase 2로 롤백 — architect가 프로파일 미발견".
- H19. task 템플릿(505-519행)의 `## 검증 명령어`가 프로파일 명령을 태스크 스코프로 채워 넣도록 되어 있다.

확인된 사실 (오케스트레이터·에이전트):

- H20. `skills/sdd-orchestrator/SKILL.md:45`: "빌드 프로파일 로드 — STATE의 `## 빌드 프로파일`을 읽는다(없으면 사용자 에스컬레이션 — Phase 2 미발견)". 워밍업은 46-50행. 프론트매터 `allowed-tools: Bash Read Write Edit Glob Grep Agent`(Skill·질문 도구 없음). 93·107행이 design/arch·ui·api 경로를 엔지니어/compliance 프롬프트에 주입. Step 4.1(164행)이 result 문서를 만든다.
- H21. `skills/sdd-orchestrator/references/state-schema.md`: 메타에 "develop 문서"(18행), 빌드 프로파일 절(25-38행)이 "arch 문서 표를 taskmaster가 복사"(26행)라고 적는다.
- H22. `agents/sdd-taskmaster.md`: 입력에 arch/ui/api 경로(15-17행), 10번 단계가 arch의 빌드 프로파일에서 명령을 읽어 `## 검증 명령어`를 채움(38행), dag 모드가 프로파일을 STATE로 복사하고 없으면 `BLOCKED`(66행). 규칙(98행)이 "arch/ui/api 문서에 없는 설계 결정 금지".
- H23. `agents/sdd-test-automator.md`: 입력에 arch 문서 전문(54행)·api 명세(61, 66, 85행), 142-144행이 "`docs/sdd/design/ui/` 존재하면 E2E 없이 DONE 금지, E2E 실패면 BLOCKED"를 강제, 183행이 "프레임워크는 arch 문서에 명시된 것 우선".
- H24. `agents/sdd-compliance-checker.md`: 입력·검증 항목에 `design/api/`, `design/ui/`, "FULL 모드"(20-23, 48-52행). `agents/sdd-reviewer.md`는 design 경로 참조가 없다(175행 "arch/컨벤션 문서 갱신 권고"는 일반 문장) — 수정 불필요.
- H25. architect 3종(`webapp-`/`flutter-`/`native-architect`)은 모두 `docs/sdd/design/arch/{date}-{feature}.md` 저장을 MUST로(각 94-97행 부근)하고, "Build Profile — REQUIRED in SDD Phase 2" 절에서 CLAUDE.md → CLAUDE.local.md → 사용자 질문 순 발견을 책임지며, webapp은 "UI and API docs do not exist yet"(23-26행)처럼 ui/api-designer 후행을 전제한다.
- H26. 삭제 대상 4종의 쓰기 경로: ui-designer → `design/ui/` + `design/DESIGN.md` + `e2e-config.json`, api-designer → `design/api/`, context-manager → `context/`, architect-reviewer는 문서를 쓰지 않는 리뷰 전용. `sdd-react-specialist`는 "UI 명세 → 코드 변환"(60-67행, 특히 62행)에서 UI 명세 문서·DESIGN.md를 입력으로 가정하므로 "spec의 UI 섹션 링크(있을 때만)"로 수정 대상이다(F14). architect 3종·`sdd-blocker-checker`(35행)의 ui/api-designer 언급도 수정 대상이다(F14).
- H27. `agents/sdd-ux-researcher.md`: tools `Read, Glob, Grep, Write, Edit`, model sonnet. 본문 절차(컨텍스트 → 요구사항 분석 → 페르소나/여정 → 유스케이스 → 경쟁 패턴 → EARS → 저장). spec "타겟 사용자/핵심 가치" 필드를 읽는 에이전트/훅은 없다.
- H28. `skills/sdd-taskrunner/SKILL.md:77`, `assets/templates/task-document.md`(5-7행 arch/ui/api 경로, 21행 arch 테스트 전략, 45행 검증 명령어)가 3종 설계 문서 경로를 전제한다.
- H29. `skills/code-mapper/SKILL.md`: 섹션 1~6 체크리스트는 115-160행(순서·레이블 고정, 117·159행), "비목표"는 165-174행(영속 금지 167행). 결정적 코어 `hooks/lib/code_mapper/format_check.py`의 `check_format_completeness()`가 자가검사한다(`tests/test_code_mapper_core.py`).
- H30. `skills/why/`, `skills/grill/`, `skills/sdd/references/`는 아직 존재하지 않는다. `skills/build-notes/`도 플러그인에 없다(사용자 전역 스킬이라는 전제와 일치).
- H31. `README.md:73`이 게이트 목록을 "spec/arch/ui/api/design/plan"으로 적는다.

확인된 사실 (테스트):

- H32. `tests/test_stop_pipeline_characterization.py`는 `_mk_state`가 `"mode": "SIMPLE"`을 기본으로 쓰고(82행), `_ALWAYS_MET_LABELS`(106-114행)와 `_KNOWN_NON_TERMINAL_LABELS`(461-478행)에 구 라벨 16개를 열거하며, PHASE2 라벨별 met/unmet 테스트(232-370행 부근, 563-663행 부근)와 `mode="FULL"/"SIMPLE"`별 `PHASE2_USER_APPROVED` 테스트(332-365, 638-665행)가 있다. 키 "집합 동일성" 단정을 금지하고 부분집합만 단정한다(493-498행). `test_decide_returns_directive_verbatim...`(117-129행)은 `DIRECTIVES[label]` 그대로 비교하므로 별칭이 같은 문자열이거나 별도 문자열이어도 통과한다.
- H33. 구 라벨명이 등장하는 테스트 위치: characterization 107, 426, 462, 512행, `tests/test_stop_pipeline_kompound_gate.py:417`(구 pipeline.json 입력 데이터로만 사용, 라벨 값은 검증 대상 아님).
- H34. 현재 `skills/*`/`agents/*` frontmatter를 검사하는 정적 테스트와 줄 수 상한 테스트는 없다(`tests/` 파일 목록 기준). 새로 만들어야 한다.

확인된 사실 (kompound-snapshot 영향, `hooks/lib/kompound_snapshot/`):

- H35. `scan.py`: 앵커(`docs/sdd`) 아래를 전수 순회하며 디렉터리 세그먼트로 kind를 정한다(`KINDS`: spec/specs/arch/ui/api/result/development/context). 존재하지 않는 디렉터리는 레코드를 만들지 않는다. `task/` 세그먼트와 `ORCHESTRATOR_STATE`·`HANDOFF`·`-GUIDE`·`DESIGN.md` 이름은 제외한다(`SKIP_NAMES`).
- H36. `registry.py`: 열 정의가 spec/arch/기타(ui·api·context 합성)/result이고 없는 kind 셀은 `—`로 채운다(441-445, 480행). `verify.py`: `KINDS` 6종 접미사로 스냅샷 집합을 정의하고 `bidirectional_count`가 raw 파일과 registry 링크의 대칭차를 검사한다(290-315행). 둘 다 어떤 kind가 "반드시 있어야 한다"는 코드는 조사 범위에서 보이지 않았다(추론).
- H37. `hooks/enforcement/kompound-snapshot-gate.sh`와 `stop-pipeline.py`의 완료 게이트는 `docs/sdd/ORCHESTRATOR_STATE.md` 존재·서명으로 무장하며 문서 종류를 세지 않는다. 따라서 문서 종류 감소로는 게이트가 깨지지 않는다(STATE 경로의 worktree 인식은 이 서술 범위 밖, R12).

확인된 사실 (도입 이력, sdd 리드 실측):

- H38. `PHASE1_UX_RESEARCH_DONE` 라벨은 `9986e2b`(2026-04-14, SDD 자동 파이프라인 컨트롤러 도입)에서 들어왔다. `agents/sdd-ux-researcher.md`는 `3955ead`(2026-04-10, 멀티에이전트 오케스트레이션 도입)에서 초기 설계로 들어왔다. 별도 근거 기록은 없다.

추론:

- I1. 문서 수가 줄어도(arch/ui/api/context 부재) scan/registry/verify/게이트는 깨지지 않는다(H35-H37). 이 서술은 문서 종류 수 변화에 한정되며, STATE 경로 소비자의 worktree 인식(R12)은 포함하지 않는다. 영향은 (a) registry의 arch 열이 새 feature 행에서 `—`가 되는 의미 변화, (b) spec 한 문서가 Phase 3에서 "구현 계획"으로 커지고 박제 시점(Phase 4 완료 후)에는 최종본 한 번만 raw가 된다는 점, 둘뿐이다.
- I2. 별칭 directive를 한 문자열로 통일하면(H2 대응) `decide()` 변경 없이 DIRECTIVES 키만 추가된다. `label_prerequisite_met`의 구 라벨 검사는 그대로 두면 구 pipeline의 "선행 파일 없음" 경고가 유지된다(구 흐름에서 이미 만들어졌을 파일이므로 정상).
- I3. 구 pipeline이 `PHASE2_UI_DESIGN_COMPLETE`/`PHASE2_API_DESIGN_COMPLETE`(사용자 승인 대기 직전)에 있었다면 별칭 directive가 해당 승인을 건너뛰게 된다. 이 건너뜀은 허용하기로 확정됐다(D7).

모름:

- U2. 구 라벨이 저장된 진행 중 `pipeline.json`을 가진 사용자 수.
- U3. `apply`가 이미 박제된 raw의 내용이 나중에 바뀐 spec(구현 계획 추가)을 만났을 때의 갱신 동작. 박제는 Phase 4 완료 뒤 1회라 이번 흐름에서는 해당 없다고 추론하나 실측하지 않았다.
- U4. (해소) 오케스트레이터 프론트매터 `allowed-tools: Bash Read Write Edit Glob Grep Agent`에 `Skill`이 없음을 리드가 실측했다. `Skill`을 추가한다(D17, F12).

### why — 근거

확인된 사실:

- W1. code-mapper는 이름 기반 가짜 확신을 줄이려고 도입됐고 ephemeral·비게이트 정체성은 영속 계약의 스테일 비용 회피에서 나왔다. 근거: `docs/sdd/spec/2026-06-26-code-mapper.md`, `docs/sdd/result/2026-06-26-code-mapper.md`.
- W2. 라벨은 전진만 가능하다(`skills/sdd/SKILL.md` 169행).
- W3. `stop-pipeline.py`는 protected 게이트 스크립트다(`CLAUDE.md` "protected set"). 이번 변경은 사용자가 명시 승인했다(2026-10-19).
- W4. `docs/lessons-learned.md`: 문서의 복사-실행 명령에 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- W5. `.harness/LEARNING.md` 2026-08-06 "커서 마커 형식 불일치": 문서에 적힌 상태값·예시 문자열이 소비 코드를 통과하는지 테스트로 고정하지 않으면 fail-safe가 불일치를 은닉한다. 이번 변경에서는 새/별칭 라벨 문자열이 `DIRECTIVES`와 directive 본문에서 서로 닫혀 있는지 테스트한다(F7, F9, F10).
- W6. `.harness/LEARNING.md` 2026-08-06 "인터프리터 경로 하드코딩": 이 spec과 산출 문서는 인터프리터 경로를 적지 않는다.
- W7. 사용자 확정(2026-10-19): `build-notes`는 사용자 전역 스킬이므로 폴백이 필수다. `Explore` 서브에이전트도 Bash가 있어 쓰기·외부 변경 금지는 프롬프트 규칙이다.

추론:

- WI1. `sdd-ux-researcher`와 Phase 2 3종 설계 문서는 제로베이스 제품 기획 흐름(idea-workshop → ux-researcher → ui/api 설계)을 전제로 설계됐을 가능성이 높다. 그 전제가 b3a7ff8로 사라졌다. 근거: 요구사항 원문 1·2, H27의 페르소나 절차, H26의 ui/api 설계 계열.

## 제약

Preserve:
- code-mapper 섹션 1~6의 순서·레이블, `check_format_completeness()`와 `hooks/lib/code_mapper/`, "비목표" 항목 전부(H29). 요구사항 없이 호출하는 기존 사용법의 출력.
- `PHASE1_SPEC_DRAFT`, `PHASE1_BLOCKER_CHECK_PASS`, `PHASE1_USER_APPROVED`, `PHASE3_TASKMASTER_DONE`, `PHASE3_DAG_CONSTRUCTED`, `PHASE3_USER_APPROVED`의 키와 의미, "라벨은 전진만 가능" 규칙(W2).
- Stop 훅의 fail-safe(미지 라벨 → 허용), 서킷 브레이커, kompound 완료 게이트 우선순위와 `decide()` Step 순서(H5).
- `label_prerequisite_met`의 기존 `checks` 항목과 `has_*` 함수(구 라벨 호환, I2). 예외: `has_tasks`·`has_orchestrator_state`는 `worktree_path` 우선·`project_dir` 폴백으로 변경(F10).
- `sdd-blocker-checker` 2단계, 사용자 승인 게이트의 존재, Phase 4 이후 흐름(오케스트레이터 Step 2~5), build-aware TDD 3원칙(워밍업 1회, per-task 증분 + 스코프, no-clean).
- `scan.py`·`registry.py`·`verify.py`와 kompound 테스트(수정하지 않는다, H35-H36).
- `e2e-gate.sh`, `hooks.json`(H10). `phase-gate.sh`는 F14가 지정한 블록 제거 외에는 바꾸지 않는다(H11).
- 사용자 원문 보존 규칙, EARS 표기, TDD 모드 FULL/SKIP 용어(H12).

Change:
- Phase 1 흐름, 에이전트 개명·삭제, spec 단일 문서 골격(F4~F6).
- 라벨 체인: `PHASE1_UX_RESEARCH_DONE` → `PHASE1_INTERVIEW_START`, Phase 2를 `PHASE2_ARCH_START`/`PHASE2_ARCH_DONE`/`PHASE2_ARCH_SKIP`으로, Phase 3에 `PHASE3_WORKTREE_CREATED` 추가, 구 PHASE2 8개 + 구 PHASE1 라벨은 별칭(F7, F9, F10).
- FULL/SIMPLE 판정 폐지와 `init_pipeline`의 `mode` 처리(F11).
- 빌드 프로파일 확보 책임을 architect/taskmaster에서 오케스트레이터(Phase 4 진입)로 이동(F12).
- E2E 정책: 설계 단계 `e2e-config.json` 생성과 "View/UI E2E 필수" 삭제, result에 수동 테스트 시나리오 기록(F13).
- 새 spec은 구 마커 대신 "미결 질문" 섹션을 쓴다. 구 마커를 소비하는 코드는 없어 호환 조항을 두지 않는다.
- 단일 문서 소비자 갱신(compliance-checker, test-automator, taskrunner 템플릿, 오케스트레이터 프롬프트, README)(F14).

Avoid:
- `DIRECTIVES`에서 구 라벨 키를 삭제하는 것(H5). 키 집합 동일성 단정 테스트(H32).
- 별칭 directive에 삭제된 에이전트명, `FULL 모드`/`SIMPLE` 문구를 남기는 것(H2).
- `[TDD == FULL]`·`tdd-gate.sh`의 TDD 모드 FULL을 설계 모드로 오인해 치환하는 것(H12).
- 인터뷰 중 사용자에게 환경에서 알 수 있는 사실을 묻는 것.
- why 스킬에 Cursor 전용 요소(모델 슬러그, `pstack-models`, `poteto`)와 서비스별 playbook을 복제하는 것.
- 코드맵 원본을 파일로 저장하는 것.
- 플러그인 파일에 사용자 홈 경로 하드코딩, 인터프리터 경로·`PATH=` prefix를 문서에 적는 것(W4, W6).
- `skills/sdd/SKILL.md`를 671줄 초과로 만드는 것.
- 템플릿 본문에 빌드/테스트 명령, 디렉터리 구조, 코드 스타일을 복사하는 것(CLAUDE.md 링크로 대체).

Risk:
- R1. 인터뷰 대기와 Stop 훅 block 충돌(H6). 대응: F8.
- R2. 자연어 승인 표가 "좋아"를 승인으로 처리해 grill yes 규칙을 약화한다(H16). 대응: F8.
- R3. 별칭 directive가 구 pipeline을 PHASE3_PLAN_START로 건너뛰게 해 UI/API 승인 대기 중이던 pipeline이 그 승인을 생략한다(I3). 허용하기로 확정됐다(D7).
- R4. `stop-pipeline.py`·`pipeline-utils.sh` 변경이 승인 범위를 넘을 위험. 대응: Boundaries의 승인 범위와 Ask first.
- R5. 서브에이전트(why/code-mapper) 결과가 길어 리드 컨텍스트를 압박한다. 대응: 사실/추론/모름 요약만 돌려받는다.
- R6. `Explore`는 Bash가 있어 쓰기·외부 변경 금지가 프롬프트 규칙이다. 도구로 강제되지 않으므로 정적 테스트는 "지침 존재"만 보장하고 준수는 보장하지 못한다(F1).
- R12. 기존 동작: 프로젝트 루트 `docs/sdd/ORCHESTRATOR_STATE.md`를 읽는 소비자(`stop-pipeline.py:449-451` kompound 완료 게이트 무장, `constants.sh:30` `HARNESS_ORCH_STATE` → `branch-gate.sh:35`, `worktree-add-gate.sh:42`, `escalation-tracker.sh:87`, `state-reader.sh` `read_orch_status`, `phase-gate.sh:26`)가 있다. STATE는 원래 worktree에 생성되므로 세션이 Phase 4에서 `EnterWorktree`로 진입하는지에 따라 이 소비자들이 휴면인지 아닌지가 갈린다. 이번 사이클은 이 소비자들을 변경하지 않으며 별도 확인 과제다.
- R7. kompound 영향(I1): 이번 범위(spec 문서 수 감소)에서 스캔·게이트는 깨지지 않지만(STATE 경로 소비자의 worktree 인식은 R12로 별도)  registry arch 열이 `—`인 feature 행이 늘어난다. 수정하지 않고 결과 문서에 기록한다.
- R8. phase-gate.sh의 Phase 2 design 판정/E2E 경고가 새 흐름에서 오경고를 낼 수 있다(H11). 해당 블록을 제거한다(F14). protected 게이트 스크립트 변경이므로 Ask first/승인 기록에 명시한다.
- R9. (해소) 오케스트레이터 `allowed-tools`에 `Skill`이 없어 `build-notes` 호출이 막힌다(U4). `Skill`을 추가한다(D17, F12).
- R10. (해소) spec 문서가 Phase 1에서 메인 체크아웃에 만들어지고 worktree는 Phase 3에서 생기므로 "구현 계획"을 쓸 위치가 정해져야 했다. `PHASE3_WORKTREE_CREATED` 진입 시 spec을 worktree 같은 경로로 이동하기로 확정됐다(D18).
- R11. 한 문서에 여러 에이전트(spec-writer, architect, taskmaster)가 순차로 쓴다. 섹션 소유권이 겹치면 덮어쓰기 위험이 있어 F5/F9/F10에서 섹션별 소유 에이전트를 고정한다.

## 기능 요구사항 (EARS)

### Wave 1 — Phase 1 (F1~F8)

### F1: why 스킬 신설 (`skills/why/`)

- THE SYSTEM SHALL `skills/why/SKILL.md`를 제공하며 frontmatter에 `name: why`와 비어 있지 않은 `description`을 둔다.
- WHEN 사용자가 코드의 설계 근거·변경 이력·회귀 원인을 묻거나 `/why`를 호출하면 THE SYSTEM SHALL 먼저 코드 앵커(대상 파일/라인, 심볼, 최근 커밋, 커밋 제목의 PR 번호)를 확보한다. 확보에는 `git blame`, `git log`, `gh pr view`(PR 본문)를 쓴다.
- THE SYSTEM SHALL source control을 항상 조사하고, WHERE Jira/Confluence/Slack 계열 MCP가 현재 환경에 있으면 해당 카테고리를 추가로 조사한다.
- IF 어떤 카테고리에 사용 가능한 MCP가 없으면 THEN THE SYSTEM SHALL 이를 조사 누락으로 결과에 한 줄 명시한다.
- THE SYSTEM SHALL 결과를 "확인된 사실 / 추론 / 모름"으로 구분하고 각 사실에 출처(커밋 해시, PR 번호, 문서 링크)를 붙인다.
- WHEN 질문이 코드 변경 선행 맥락이면 THE SYSTEM SHALL 결과를 Preserve / Change / Avoid / Risk로 변환해 덧붙인다.
- THE SYSTEM SHALL 조사 전용으로 동작한다. SKILL.md에 읽기 전용 규칙을 명시하고 금지 대상(파일 쓰기, 커밋·푸시, 이슈·PR 코멘트·메시지 전송 등 외부 시스템 변경)을 열거한다.
- THE SYSTEM SHALL references를 정확히 3개로 제한한다: (1) source control 가이드, (2) 사실/추론/모름 에피스테믹 가이드, (3) Jira/Confluence/Slack을 아우르는 카테고리 가이드 1개. 서비스별 playbook과 Cursor 전용 요소를 복제하지 않는다.
- WHEN why가 sdd Phase 1에서 호출되면 THE SYSTEM SHALL `subagent_type: Explore` 서브에이전트로 실행한다. 단독 `/why`도 지원한다.
- Acceptance (오프라인 pytest):
  - `skills/why/SKILL.md` 존재, frontmatter `name == "why"`, `description` 비어 있지 않음. `skills/why/references/*.md`가 정확히 3개. SKILL.md에 `Preserve`, `Change`, `Avoid`, `Risk` 포함.
  - SKILL.md에 읽기 전용 규칙 키워드(`읽기 전용`, `파일 쓰기`, `외부 시스템`)가 있음(R6: 지침 존재만 검사).
  - `skills/why/` 하위 모든 `*.md`에 정규식 `(?i)\b(grok|gpt-?\d|gemini|claude[-\w.]*(opus|sonnet|haiku|fable))` 매치가 없고 `pstack-models`, `poteto` 문자열도 없음.
  - 같은 테스트가 정규식 자체를 샘플로 검증한다. 매치해야 하는 샘플: `claude-4.5-opus-high`, `claude-3-5-sonnet`, `gpt4o`, `gpt-5`, `grok-4`, `claude-opus-4-1`, `gemini-2.5-pro`. 매치하면 안 되는 샘플: `claude-code`, `Claude Code`, `claude-api`, `sonnet 모델`.
- Acceptance (수동): 이력이 있는 임의 파일에 `/why`를 실행하면 코드 앵커 → 사실/추론/모름 → 누락 카테고리 한 줄 순서로 출력된다.

### F2: grill 스킬 신설 (`skills/grill/`)

- THE SYSTEM SHALL `skills/grill/SKILL.md`를 제공하며 frontmatter에 `name: grill`과 비어 있지 않은 `description`을 둔다.
- WHEN 사용자가 계획·결정·요구사항 검증을 요청하거나 `/grill`을 호출하면 THE SYSTEM SHALL mattpocock grilling 형식으로 frontier 라운드를 진행한다: 선행 결정이 모두 확정된 질문을 한 라운드에 모아 번호와 추천 답과 함께 묻고, 다른 미결 질문에 의존하는 질문은 다음 라운드로 미룬다. 개별 질문에 사용자가 "네"라고 하면 추천 답 수락이다.
- THE SYSTEM SHALL 환경에서 알 수 있는 사실을 사용자에게 묻지 않고 직접 조사한다. sdd 안에서는 why / code-mapper를 `subagent_type: Explore`로 보낸다.
- WHEN 다음 사용자 답 3개를 예측할 수 있는 상태가 되면 THE SYSTEM SHALL 질문을 종료하고 요약 단계로 간다. SKILL.md에 예시 문장을 둔다: "다음에 물을 질문 3개를 적었을 때 각각 사용자 답을 추천 답 그대로 예측할 수 있으면 종료".
- WHEN 질문을 종료하면 THE SYSTEM SHALL "하지 않을 것"을 포함한 5~8줄 요약을 제시하고 명시적 yes를 요구한다.
- IF 요약에 대한 응답이 "좋아 보여" 같은 암묵적 동의이면 THEN THE SYSTEM SHALL 승인으로 취급하지 않고 요약 수정 또는 yes 재요청을 한다.
- IF 세션이 비대화형(`/loop`, 스케줄, CI)이면 THEN THE SYSTEM SHALL grill을 시작하지 않고 사용자 입력이 필요하다고 보고한다.
- THE SYSTEM SHALL interview-me에서 요약 5~8줄과 "하지 않을 것", 명시적 yes 게이트, 답 3개 예측 시 종료, 비대화형 미사용만 채택하고 한 번에 한 질문 방식은 채택하지 않는다.
- THE SYSTEM SHALL 단독 호출(`/grill`)을 지원하며 pipeline 상태를 다루지 않는다.
- Acceptance (오프라인 pytest): `skills/grill/SKILL.md` 존재, frontmatter 유효. 본문에 `frontier`, `하지 않을 것`, 비대화형 지침, 명시적 yes 지침, 예시 문장 키워드가 있음. `pipeline.json`, `advance_label`, `set_waiting_for_user` 문자열이 없음.
- Acceptance (수동): 모호한 요구사항으로 `/grill` 실행 시 번호+추천 답 라운드가 나오고, "좋아 보여"에는 게이트가 열리지 않으며 "yes"에는 열린다.

### F3: code-mapper 확장 — 구현 걸림돌 블록

- WHEN code-mapper가 요구사항과 함께 호출되면 THE SYSTEM SHALL 섹션 1~6 뒤에 별도 블록 "구현 걸림돌"을 추가한다. 내용: 영향받는 호출자, 깨질 수 있는 불변식·테스트, 제약을 거는 기존 구조.
- WHEN 요구사항 없이 호출되면 THE SYSTEM SHALL 기존 출력과 동일하게 동작한다.
- THE SYSTEM SHALL 섹션 1~6의 순서·레이블과 `check_format_completeness()`를 변경하지 않고, code-mapper 자체는 여전히 저장하지 않는다. 요약·근거는 spec-writer가 spec "코드 조사"에 기록한다.
- Acceptance (오프라인 pytest): `tests/test_code_mapper_core.py` 수정 없이 통과. SKILL.md의 "비목표" 절이 남아 있고 "영속 금지" 문구 유지. SKILL.md에 "구현 걸림돌"과 "요구사항이 주어졌을 때만" 조건이 있음. `hooks/lib/code_mapper/`가 변경되지 않음(`git diff --stat` 무변경 확인은 결과 문서에 기록).

### F4: SDD Phase 1 = 인터뷰 단계

- WHEN 사용자가 SDD를 시작하면(제로베이스 포함, 건너뛰기 분기 없음) THE SYSTEM SHALL 동일한 흐름을 따른다: 요구사항 → grill(필요 시 why/code-mapper 조사) → 요약 → 명시적 yes → `sdd-spec-writer` → `sdd-blocker-checker` → 승인.
- THE SYSTEM SHALL 별도 리서치 단계를 두지 않는다. 조사는 인터뷰 중 필요할 때만 why / code-mapper를 `subagent_type: Explore`로 보내 수행한다.
- WHEN 사용자가 요약에 명시적 yes를 하면 THE SYSTEM SHALL `sdd-spec-writer`를 디스패치한다. 입력은 grill 확정 요약, 조사 결과 요약, 사용자 원문이다.
- WHEN spec 작성이 끝나면 THE SYSTEM SHALL 기존 흐름(`sdd-blocker-checker` 1차(플랫폼/스택 확인)/2차 → 사용자 승인 게이트)을 그대로 따른다.
- IF 세션이 비대화형이면 THEN THE SYSTEM SHALL Phase 1을 멈추고 사용자 입력이 필요하다고 보고한다.
- THE SYSTEM SHALL `skills/sdd/SKILL.md`의 Phase 1 프로세스, 에이전트 표, 상태머신, Phase 2 진입 전 검증 1번 롤백 대상(`sdd-spec-writer`, 인터뷰가 필요하면 Phase 1 인터뷰로 롤백)을 새 흐름으로 갱신한다.
- Acceptance (오프라인 pytest): `skills/sdd/SKILL.md`가 `grill`, `why`, `code-mapper`, `sdd-spec-writer`, `subagent_type: Explore`, 비대화형 지침을 포함. 스캔 범위(`skills/`, `agents/`, `hooks/`, `.claude-plugin/`, `README.md`, `CLAUDE.md`)에서 `ux-researcher` 문자열이 0건.

### F5: spec 작성 에이전트 개명·축소 (`agents/sdd-spec-writer.md`)

- THE SYSTEM SHALL `agents/sdd-ux-researcher.md`를 `agents/sdd-spec-writer.md`로 개명하고 `name: sdd-spec-writer`로 바꾸며 frontmatter `tools`에 `Write`를 둔다. 페르소나/여정/유스케이스/경쟁 패턴 절차를 제거한다.
- WHEN 호출되면 THE SYSTEM SHALL 입력으로 새 spec 골격(F6)의 단일 문서를 `docs/sdd/spec/{YYYY-MM-DD}-{feature}.md`에 Write로 직접 저장한다. 파일로 저장하지 않고 내용만 반환하는 것은 완료가 아니다.
- THE SYSTEM SHALL 새 기능 설계(구조·알고리즘)는 쓰지 않는다. 기존 코드 사실·제약은 근거(파일:라인, 커밋, PR)와 함께 쓴다. 근거 없는 항목은 "추론" 또는 "모름"으로 표기한다.
- THE SYSTEM SHALL 사용자 원문을 변형하지 않고, 모호성은 "미결 질문"에 둔다(인터뷰 확정 후이므로 새로 발견한 것만). 구 마커는 쓰지 않는다.
- THE SYSTEM SHALL "적용 규칙"에 프로젝트에 로드된 규칙(CLAUDE.md, ANTI_SLOP 등) 중 이번 변경에 걸리는 것만 쓴다. 사용자 홈 경로를 하드코딩하지 않는다.
- THE SYSTEM SHALL `BLOCKER_PASS` 마크 처리(`PHASE1_SPEC_DRAFT` directive 의존, `has_blocker_pass` 리터럴 검사)를 기존대로 유지한다.
- THE SYSTEM SHALL spec "기능 요구사항"·"설계 결정"·"미결 질문" 섹션의 소유자이며 "구현 계획" 섹션은 쓰지 않는다(R11).
- Acceptance (오프라인 pytest): `agents/sdd-spec-writer.md` 존재, frontmatter `name == "sdd-spec-writer"`, `tools`에 `Write` 포함, `agents/sdd-ux-researcher.md` 부재. 본문에 `페르소나`, `유스케이스`, `타겟 사용자`가 없고 "미결 질문"이 있음.

### F6: 단일 문서 골격과 템플릿 분리

- THE SYSTEM SHALL 새 SDD 사이클에서 spec·arch·ui·api·context를 `docs/sdd/spec/{YYYY-MM-DD}-{feature}.md` 한 문서로 통합한다. task 문서(`docs/sdd/task/...`)와 `ORCHESTRATOR_STATE.md`는 별도로 유지한다.
- THE SYSTEM SHALL `docs/sdd/design/`와 `docs/sdd/context/`를 새로 만들지 않는다.
- THE SYSTEM SHALL 템플릿 본문을 `skills/sdd/references/spec-template.md`로 분리하고 `skills/sdd/SKILL.md`에는 그 파일을 가리키는 참조 한 줄만 둔다.
- THE SYSTEM SHALL 템플릿에 13개 섹션을 이 순서로 담는다: 목표 / 사용자 요구사항(원문) / 가정 / 코드 조사 / 제약(Preserve·Change·Avoid·Risk) / 기능 요구사항(EARS + 각 F의 Acceptance) / 설계 결정 / 테스트 전략 / 적용 규칙 / 빌드·테스트 명령 / Boundaries(Always·Ask first·Never) / 범위 밖 / 미결 질문.
- THE SYSTEM SHALL 조건부 섹션 3개를 템플릿에 둔다: `## 기능 지도`(요청이 독립 기능 여러 개일 때만, 맨 앞), `## UI`(이미 나온 디자인이 있을 때만, 링크만), `## 구현 계획`(Phase 3에서 taskmaster가 작성: 순서·위험·테스트 스코프).
- THE SYSTEM SHALL "빌드·테스트 명령", "구조", "스타일"은 복사하지 않고 CLAUDE.md 링크로 대체하며 경로를 하드코딩하지 않는다. "적용 규칙"에는 로드된 규칙 중 이번 변경에 걸리는 것만 적는다.
- THE SYSTEM SHALL "타겟 사용자", "핵심 가치" 필드를 제거한다(H27).
- THE SYSTEM SHALL 새 템플릿과 `sdd-spec-writer`가 `BLOCKER_PASS` 마크를 유지하게 한다(`PHASE1_SPEC_DRAFT` directive가 의존하며 `has_blocker_pass`가 리터럴로 검사한다).
- Acceptance (오프라인 pytest): `skills/sdd/references/spec-template.md`에 위 13개 섹션 제목과 `기능 지도`, `UI`, `구현 계획` 조건부 섹션 제목, `Preserve`, `Change`, `Avoid`, `Risk`, `Always`, `Ask first`, `Never`가 있고 `타겟 사용자`, `핵심 가치`는 없음. `skills/sdd/SKILL.md`가 `references/spec-template.md`를 참조하고 `타겟 사용자`, `핵심 가치`를 포함하지 않음. `skills/`·`agents/` 하위에 `docs/sdd/design/`, `docs/sdd/context/` 경로 지시 문자열 0건.

### F7: Phase 1 라벨과 하위호환

- THE SYSTEM SHALL `stop-pipeline.py`의 `DIRECTIVES`에 `PHASE1_INTERVIEW_START` 키를 추가한다. directive는 인터뷰 흐름(F4), 대기 규칙(F8), `sdd-spec-writer` 디스패치, 완료 후 `PHASE1_SPEC_DRAFT` 갱신을 지시한다.
- THE SYSTEM SHALL `PHASE1_UX_RESEARCH_DONE`를 `DIRECTIVES`에 별칭으로 남겨 `PHASE1_INTERVIEW_START`와 같은 directive를 준다.
- THE SYSTEM SHALL `init_pipeline`의 초기 라벨을 `PHASE1_INTERVIEW_START`로 바꾼다.
- THE SYSTEM SHALL 어떤 directive 본문에도 `ux-researcher` 문자열을 넣지 않는다.
- THE SYSTEM SHALL `tests/test_stop_pipeline_characterization.py`와 `tests/test_stop_pipeline_kompound_gate.py`를 새 라벨에 맞게 갱신한다. 기대값을 약화하지 않고(단정 삭제 금지) 새 라벨로 치환하며 별칭 단정을 추가한다.
- Acceptance (오프라인 pytest): 새 라벨과 구 라벨 모두 `DIRECTIVES`에 있고 두 directive가 동일하며 `ux-researcher`를 포함하지 않음. `decide()`가 두 라벨에서 `{"decision": "block", "reason": DIRECTIVES[label]}`를 반환하고 구 라벨이 저장된 `pipeline.json`에서도 block 유지. `waiting_for_user=True`이면 두 라벨 모두 `continue: True`. `init_pipeline` 실행 결과 `current_label == "PHASE1_INTERVIEW_START"`. 키 집합 동일성 단정 없음.

### F8: 인터뷰 대기와 승인 정합

- WHEN sdd 리드가 grill 질문 턴을 끝내려 하면 THE SYSTEM SHALL 그 전에 `set_waiting_for_user true interview`를 호출한다(순서가 뒤집히면 Stop 훅이 block을 재주입한다).
- THE SYSTEM SHALL pipeline 상태 호출을 sdd 리드(`skills/sdd/SKILL.md`)의 책임으로 두고 grill SKILL.md는 pipeline 상태를 다루지 않는다(F2 Acceptance).
- WHEN 사용자가 응답하면 THE SYSTEM SHALL `waiting_for_user=false`로 되돌리고 인터뷰를 이어간다. WHEN 요약 승인에 "좋아" 등 yes가 아닌 응답이 와서 yes를 재요청하면 THE SYSTEM SHALL 재요청 턴을 끝내기 전에 다시 `set_waiting_for_user true interview`를 먼저 호출한다. WHEN 사용자가 요약에 명시적 yes를 하면 THE SYSTEM SHALL `waiting_for_user=false`로 하고 spec-writer를 디스패치한다.
- WHILE 인터뷰 요약 승인 대기 중이면(`waiting_for_approval_type='interview'`) THE SYSTEM SHALL 요약 승인을 "네" 또는 "yes" 단독 응답일 때만 인정하고, "좋아", "ok", "진행" 같은 응답에는 yes를 재요청한다. 개별 질문 라운드에서의 "네"는 추천 답 수락으로 별도 정의한다.
- THE SYSTEM SHALL 이 예외를 `skills/sdd/SKILL.md` 자연어 승인 표(44-52행) 바로 아래 한 줄로만 기록하고 표의 다른 단계 처리는 바꾸지 않는다.
- Acceptance (오프라인 pytest): `PHASE1_INTERVIEW_START` + `waiting_for_user=True`에서 `decide()`가 `continue: True`. `skills/sdd/SKILL.md`에 `set_waiting_for_user true interview` 지침과 "네"/"yes" 단독 예외 한 줄이 있고, 그 줄이 자연어 승인 표 직후에 위치함.
- Acceptance (수동): 인터뷰 질문 턴 직후 Stop 훅이 block하지 않고, 답변 후 재개된다.

### Wave 2 — Phase 2·3과 공통 (F9~F15)

### F9: Phase 2 — 조건부 아키텍처

- WHEN `PHASE1_USER_APPROVED`가 되면 THE SYSTEM SHALL 리드가 spec "설계 결정"을 보고 아키텍처 변경 필요 여부를 판단하고, 필요하면 `PHASE2_ARCH_START`, 불필요하면 `PHASE2_ARCH_SKIP`으로 전이한다.
- WHEN `PHASE2_ARCH_START`이면 THE SYSTEM SHALL 프로젝트 스택에 맞는 architect(`webapp-`/`flutter-`/`native-architect`)를 디스패치해 같은 문서의 "설계 결정" 섹션을 보강하게 하고 완료 시 `PHASE2_ARCH_DONE`으로 전이한다. Phase 2는 worktree 생성(Phase 3) 전이므로 architect는 메인 체크아웃의 spec 파일을 보강한다(D18). 별도 승인 게이트는 없다(Phase 3 승인에 포함).
- WHEN `PHASE2_ARCH_DONE` 또는 `PHASE2_ARCH_SKIP`이면 THE SYSTEM SHALL `PHASE3_PLAN_START`로 전이하도록 지시한다.
- THE SYSTEM SHALL architect 3종에서 `docs/sdd/design/arch/` 저장 지시, 빌드 프로파일 발견 책임("Build Profile — REQUIRED")을 제거하고 "같은 문서의 설계 결정 섹션만 보강, 새 파일 금지"로 바꾼다. 테스트 전략(프레임워크·레이어별 테스트 타입) 지침은 유지한다.
- THE SYSTEM SHALL `sdd-ui-designer`, `sdd-api-designer`, `sdd-architect-reviewer`, `sdd-context-manager`를 삭제한다.
- THE SYSTEM SHALL 구 PHASE2 라벨 8개(H1)를 `DIRECTIVES`에 별칭으로 남기되 하나의 공통 directive 문자열을 쓴다. 문구는 "구 라벨(하위호환), 이미 생성된 design/·context/ 문서는 수정하지 말고 `current_label`을 `PHASE3_PLAN_START`로 갱신"을 지시하며 삭제된 에이전트명과 FULL/SIMPLE 문구를 포함하지 않는다.
- Acceptance (오프라인 pytest): `DIRECTIVES`에 `PHASE2_ARCH_START`, `PHASE2_ARCH_DONE`, `PHASE2_ARCH_SKIP`과 구 PHASE2 8개 키가 모두 있음. `PHASE1_USER_APPROVED` directive가 `PHASE2_ARCH_START`와 `PHASE2_ARCH_SKIP`을 모두 언급. `PHASE2_ARCH_START` directive가 `PHASE2_ARCH_DONE`, `PHASE2_ARCH_DONE`/`PHASE2_ARCH_SKIP` directive가 `PHASE3_PLAN_START`를 언급. 구 PHASE2 8개 별칭 directive는 서로 동일하고 `PHASE3_PLAN_START`를 언급. 모든 `DIRECTIVES` 본문에 삭제된 에이전트 4종 이름이 없음. 구 PHASE2 라벨이 저장된 `pipeline.json`에서 `decide()`가 block + `DIRECTIVES[label]`(선행 파일 미충족이면 기존 경고 접미사)를 반환. `agents/`에 삭제 4종 파일 부재. 스캔 범위에서 삭제 에이전트 4종 이름 0건. architect 3종 본문에 `docs/sdd/design/arch/`와 `Build Profile` 문자열이 없음.

### F10: Phase 3 — worktree 이동과 구현 계획

- WHEN `PHASE3_PLAN_START`이면 THE SYSTEM SHALL `Skill(git-worktree)`로 `feature/{feature}` worktree를 생성하게 하고 `worktree_path`를 기록한 뒤 `PHASE3_WORKTREE_CREATED`로 전이하도록 지시한다. IF `pipeline.json`에 `worktree_path`가 이미 있고 디렉터리가 존재하면 THEN THE SYSTEM SHALL 생성을 건너뛰고 바로 `PHASE3_WORKTREE_CREATED`로 전이하도록 지시한다(구 pipeline 호환).
- WHEN `PHASE3_WORKTREE_CREATED`에 진입하면 THE SYSTEM SHALL 승인된 spec 파일을 메인 체크아웃에서 worktree의 같은 상대 경로(`docs/sdd/spec/{date}-{feature}.md`)로 이동한다(복사 아님). 메인 체크아웃의 spec은 미커밋 파일이므로 이동 후 정본은 worktree의 파일 하나다. 세 경우로 나눈다: (a) worktree에 같은 경로 파일이 없으면 이동(`mv`)한다. (b) 있고 `cmp`로 메인 사본과 동일하면 메인 사본을 삭제하고 진행한다. (c) 있고 내용이 다르면 전이를 멈추고 `waiting_for_user=true`로 사용자에게 보고한다. 어느 쪽이 정본인지 임의로 결정하지 않는다.
- WHEN `PHASE3_WORKTREE_CREATED`이면 THE SYSTEM SHALL `sdd-taskmaster`(mode `tasks`)를 디스패치해 같은 spec 문서에 `## 구현 계획`(순서·위험·테스트 스코프)을 쓰고 task 문서를 만들게 한 뒤 `PHASE3_TASKMASTER_DONE`으로 전이하도록 지시한다.
- THE SYSTEM SHALL Phase 3 산출물(task 문서, `ORCHESTRATOR_STATE.md`)을 worktree에 쓴다(한 곳에 고정: worktree의 `docs/sdd/task/`, `docs/sdd/ORCHESTRATOR_STATE.md`). 이는 기존 동작이다: 구 흐름도 Phase 2 진입 시 worktree를 만들고 "Phase 2, 3, 4의 모든 작업은 worktree 내에서 수행"(`skills/sdd/SKILL.md:274`)하므로 STATE는 원래 worktree에 생성됐다. 이번 변경은 worktree 생성 시점(Phase 2→3)만 바꾸고 STATE 위치는 바꾸지 않는다.
- THE SYSTEM SHALL `label_prerequisite_met`의 `checks`에 `PHASE3_WORKTREE_CREATED: has_worktree`를 추가한다. 기존 `checks` 항목은 바꾸지 않는다. 단 예외 두 항목: `has_tasks`·`has_orchestrator_state` 검사는 `pipeline.json`의 `worktree_path`가 있으면 그 경로 기준으로, 없으면 `project_dir`로 폴백해 파일을 찾도록 변경한다(구 pipeline 호환). 이를 위해 두 함수의 시그니처에 worktree 경로 인자를 추가한다(`stop-pipeline.py:229-234`).
- THE SYSTEM SHALL `PHASE3_DAG_CONSTRUCTED`의 사용자 승인을 "plan + tasks" 승인으로 유지한다(`approval_type='plan'`). 사용자 승인은 Phase 1과 Phase 3 두 번뿐이다.
- THE SYSTEM SHALL `sdd-taskmaster`의 입력을 spec 단일 문서 경로 + worktree 경로 + feature 이름 + 모드로 바꾸고, 문서에 없는 설계 결정을 임의로 하지 않는 규칙을 spec 기준으로 유지한다.
- THE SYSTEM SHALL taskmaster가 빌드 프로파일을 찾지 않게 한다. task 문서에는 테스트 스코프(필터 대상)만 쓰고 실제 빌드·테스트 명령은 쓰지 않는다. dag 모드는 프로파일을 STATE로 복사하지 않으며 프로파일 부재로 `BLOCKED`를 반환하지 않는다.
- THE SYSTEM SHALL worktree 절 이동에 맞게 `skills/sdd/SKILL.md`의 "Phase 2 진입: worktree 격리"를 Phase 3 진입으로 옮기고 Phase 3 진입 전 검증(2~5번)을 단일 문서 기준(spec 존재 + BLOCKER_PASS + Phase 1 승인 기록 + 아키텍처 보강 여부 기록)으로 교체한다.
- Acceptance (오프라인 pytest): `PHASE3_WORKTREE_CREATED` 키가 `DIRECTIVES`에 있고 `PHASE3_TASKMASTER_DONE`을 언급. `PHASE3_PLAN_START` directive가 `Skill(git-worktree)`, `worktree_path`, `PHASE3_WORKTREE_CREATED`를 언급. `PHASE3_WORKTREE_CREATED` directive가 spec 이동(복사 아님)과 worktree 경로 기준 taskmaster 입력을 언급하고 `복사`로 지시하지 않으며, 세 경우(없음 → `mv`, 있고 `cmp` 동일 → 메인 사본 삭제 후 진행, 있고 다름 → 전이 중단 + `waiting_for_user=true` 사용자 보고, 정본 임의 결정 금지)를 각각 지시함. worktree에 `T-*.md`를 만든 뒤 `PHASE3_TASKMASTER_DONE`이 met, worktree에 `ORCHESTRATOR_STATE.md`를 만든 뒤 `PHASE3_DAG_CONSTRUCTED`가 met(`worktree_path` 없으면 `project_dir` 폴백도 각각 검증). `PHASE3_WORKTREE_CREATED` + `worktree_path` 미존재에서 `decide()`가 block + 기존 형식의 경고 접미사(기존 테스트 방식(characterization 테스트)으로 검증), 존재하면 경고 없음. `PHASE3_TASKMASTER_DONE` 이후 directive 문자열이 기존과 동일. `agents/sdd-taskmaster.md`에 `design/arch`, `design/ui`, `design/api`, `FULL 모드`가 없고, 정규식 `프로파일.*BLOCKED` 매치가 0건이며(79행의 일반 반환 계약 `DONE | NEEDS_CONTEXT | BLOCKED`는 유지), `구현 계획`이 있음.

### F11: FULL/SIMPLE 판정 폐지

- THE SYSTEM SHALL 설계 모드(FULL/SIMPLE) 판정과 그에 따른 분기를 `skills/sdd/SKILL.md`, `stop-pipeline.py` 새 directive, `pipeline-utils.sh`, `sdd-compliance-checker`, `sdd-taskmaster`에서 제거한다.
- THE SYSTEM SHALL `init_pipeline <feature>`를 기본 호출형으로 하고 구 호출형 `init_pipeline <feature> <FULL|SIMPLE>`도 오류 없이 받되 두 번째 인자를 무시한다. 새로 만드는 `pipeline.json`에는 `mode` 키를 쓰지 않고 완료 메시지에 모드를 출력하지 않는다. `show_pipeline`은 `mode`가 있을 때만 출력한다.
- THE SYSTEM SHALL 구 `pipeline.json`의 `mode` 값을 읽기 전용 호환으로만 소비한다(`PHASE2_USER_APPROVED`의 `has_context` 분기, H4 — 코드 변경 없음).
- THE SYSTEM SHALL `sdd-compliance-checker`가 spec 단일 문서의 설계 결정·UI 링크·기능 요구사항을 기준으로 검증하게 한다(`design/api/`, `design/ui/`, "FULL 모드" 삭제).
- Acceptance (오프라인 pytest, 임시 `CLAUDE_PROJECT_DIR`): `init_pipeline demo`와 `init_pipeline demo FULL` 모두 종료 코드 0이고 생성된 `pipeline.json`에 `mode` 키가 없음. `show_pipeline`이 `mode` 없는 JSON에서 오류 없이 동작. 스캔 범위에서 `SIMPLE` 문자열 0건(단, `[TDD == FULL]`·`tdd-gate.sh` 등 TDD 모드 사용은 대상 아님), `skills/sdd/SKILL.md`·`agents/sdd-compliance-checker.md`·`agents/sdd-taskmaster.md`에 `FULL 모드` 0건. `PHASE2_USER_APPROVED` + `mode="FULL"` 기존 테스트가 그대로 통과.

### F12: 빌드 프로파일 확보를 Phase 4 진입으로 이동

- WHEN Phase 4가 진입되면(오케스트레이터 Step 1) THE SYSTEM SHALL 빌드 프로파일을 아래 순서로 확보하고 `ORCHESTRATOR_STATE.md`의 `## 빌드 프로파일`에 기록한다: (1) STATE에 이미 있으면 사용, (2) `CLAUDE.md`, (3) `CLAUDE.local.md`, (4) `/build-notes` 스킬이 사용 가능하면 실행해 `CLAUDE.local.md`에 기록하게 한 뒤 STATE로 옮김, (5) 그래도 없으면 사용자에게 질문.
- IF 빌드 명령 확보 Step (5)의 사용자 질문이 불가능한 컨텍스트(sdd-team-leader, Agent Team 팀원)이면 THEN THE SYSTEM SHALL `BLOCKED`를 반환해 리드가 사용자에게 질문을 중계하게 한다.
- THE SYSTEM SHALL `build-notes`를 사용자 전역 스킬로 취급해 부재를 정상 경로로 다루고 (5)로 폴백한다. 플러그인에 `build-notes`를 이관하지 않는다.
- THE SYSTEM SHALL `skills/sdd/SKILL.md` Phase 4 진입 검증 5번("프로파일 없음 → Phase 2 롤백")을 이 절차로 교체하고 "프로파일 발견(Phase 2, architect)" 절과 스키마 위치 설명을 오케스트레이터 기준으로 고친다.
- THE SYSTEM SHALL build-aware TDD 3원칙(워밍업 1회, per-task 증분 빌드 + 스코프 테스트, no-clean)과 프로파일 스키마 표를 유지한다.
- THE SYSTEM SHALL `skills/sdd-orchestrator/references/state-schema.md`의 빌드 프로파일 안내를 "오케스트레이터가 Phase 4 진입 시 기록"으로 바꾸고 메타의 구 "develop 문서" 항목을 spec 단일 문서로 바꾼다.
- THE SYSTEM SHALL `skills/sdd-orchestrator/SKILL.md` frontmatter `allowed-tools`에 `Skill`을 추가해 `/build-notes` 호출이 막히지 않게 한다(D17).
- Acceptance (오프라인 pytest): `skills/sdd-orchestrator/SKILL.md` frontmatter `allowed-tools`에 `Skill`이 포함됨. 같은 파일 Step 1에 확보 순서 키워드(`CLAUDE.md`, `CLAUDE.local.md`, `/build-notes`, 사용자 질문)가 순서대로 있고 "Phase 2 미발견" 문구가 없음. `skills/sdd/SKILL.md`에 "Phase 2로 롤백 — architect가 프로파일 미발견" 문구가 없고 워밍업·증분·no-clean 3원칙이 남아 있음. `state-schema.md`에 `taskmaster가 복사` 문구가 없음. 스캔 범위에서 `rg -n "docs/sdd/design/arch|Build Profile|arch 문서의 .*## 빌드 프로파일|taskmaster가 복사" skills agents hooks --glob '!hooks/lib/kompound_snapshot/**'` 결과 0건(단 구 라벨 호환용 `hooks/enforcement/stop-pipeline.py:217-227`의 `has_arch`/`has_ui`/`has_api`/`has_context`는 유지하므로 검사 제외, 218행의 구 라벨 호환 `has_arch` 줄 포함). 엔지니어 에이전트의 "빌드 프로파일로 증분 빌드" 류 문구는 유지된다.

### F13: E2E 정책 변경

- THE SYSTEM SHALL 설계 단계에서 `enabled` 설정을 만들지 않는다(`sdd-ui-designer` 삭제). 기본 `e2e-config.json`(`enabled: false`)은 `init-state.sh`가 계속 생성하므로 e2e-gate는 휴면 상태다. `skills/sdd/SKILL.md` 문서 구조의 `e2e-config.json` 항목과 "View/UI 구현 전 E2E RED" 규칙(369, 373행)을 삭제한다.
- THE SYSTEM SHALL `sdd-test-automator`의 "E2E 필수 확인 — UI 있으면 E2E 없이 DONE 금지"(142-144행)를 삭제하고 입력의 arch/api 명세 참조를 spec 단일 문서 기준으로 고친다.
- WHERE 변경이 UI를 포함하면(spec에 `## UI` 섹션이 있거나 task 문서 테스트 타입에 E2E/UI가 있으면) THE SYSTEM SHALL 오케스트레이터가 Phase 4 result 문서에 수동 테스트 시나리오를 기록한다. 개발자가 수동 확인한 뒤 요청할 때만 E2E를 작성한다.
- THE SYSTEM SHALL `e2e-gate.sh`를 수정하지 않는다(설정이 없으면 통과하는 휴면 상태, H10).
- Acceptance (오프라인 pytest): `skills/sdd/SKILL.md`와 `agents/sdd-test-automator.md`에 `E2E 필수`, `E2E 없이 DONE`, `e2e-config` 문자열 0건. `skills/sdd-orchestrator/SKILL.md`와 `skills/sdd/references/spec-template.md`에 `수동 테스트 시나리오`가 있음. `hooks/enforcement/e2e-gate.sh`가 변경되지 않음(결과 문서에 diff 무변경 기록).

### F14: 단일 문서 소비자 갱신

- THE SYSTEM SHALL 아래 파일의 `design/arch|ui|api`, `context`, `arch 문서`, `ui/api 명세` 참조를 spec 단일 문서 참조로 바꾼다: `skills/sdd-orchestrator/SKILL.md`(93, 107행), `skills/sdd-taskrunner/SKILL.md`(77행), `skills/sdd-taskrunner/assets/templates/task-document.md`(5-7, 21, 45행), `agents/sdd-compliance-checker.md`, `agents/sdd-test-automator.md`, `agents/sdd-taskmaster.md`, `README.md`(73행 게이트 목록).
- THE SYSTEM SHALL `skills/sdd/SKILL.md`의 문서 구조, Phase 판정 규칙(정밀 모드/context 의존 제거, 단일 문서 + task + STATE 기준 표), 상태머신, 에이전트 표, 게이트 정책, 스펙 변경 정책, task 템플릿(`## 검증 명령어` → 테스트 스코프만), 하위호환 문장을 새 흐름으로 갱신한다.
- THE SYSTEM SHALL `hooks/enforcement/phase-gate.sh`(protected 게이트 스크립트)에서 다음을 제거한다: Phase 2 design 판정 블록(`DESIGN_DIR`, `HAS_ARCH`/`HAS_UI`/`HAS_API`, `2_done`), "Phase 3 태스크가 있지만 Phase 2 architecture 설계 문서가 없습니다" 경고, UI 명세/e2e-config 경고 블록(약 96-104행). `CONTEXT_DIR` 의존(SDD 미시작 판정)은 `SPEC_DIR` 기준으로 정리한다. design 블록 제거 후 남는 검사는 spec 존재, task 존재, `4_active`일 때 task 문서 존재다. 경고만 하는 훅이라는 성격은 유지한다.
- THE SYSTEM SHALL 구 라벨 예시·주석의 경로 문자열을 갱신한다: `hooks/enforcement/stop-pipeline.py` 370행 주석은 경로 없이 고쳐 쓴다, `hooks/enforcement/lib/logging.sh:19`의 예시 문자열과 `hooks/enforcement/lib/pipeline-utils.sh:9` 주석의 구 라벨 예시를 새 라벨로 바꾼다. 구 라벨 호환용 `stop-pipeline.py:217-227`의 `has_arch`/`has_ui`/`has_api`/`has_context`는 Preserve에 따라 유지한다.
- THE SYSTEM SHALL 아래 파일의 설계 문서 후행 전제를 바꾼다. `agents/webapp-architect.md`(24, 26행), `agents/flutter-architect.md`(25, 27행), `agents/native-architect.md`(24, 26행): "ui-designer/api-designer가 후속으로 사용" 전제 문장을 "spec 설계 결정 보강"으로 교체. `agents/sdd-blocker-checker.md`(35행): ui-designer 언급을 "Phase 2·3 설계 단계"로. `agents/sdd-react-specialist.md`(62행): UI 명세 문서·DESIGN.md 입력 가정을 "spec의 UI 섹션 링크(있을 때만)"로. `CLAUDE.md`(15행 "spec/design/task/result")와 `README.md`(73행)도 갱신한다.
- THE SYSTEM SHALL `scan.py`, `registry.py`, `verify.py`, kompound 게이트와 그 테스트를 수정하지 않고, 영향 조사 결과(I1)를 결과 문서와 spec Risk(R7)에 기록한다.
- THE SYSTEM SHALL 이미 완료된 사이클 산출물(`docs/sdd/**` 과거 문서, `docs/multi-agent-plan.md`, 엔지니어 에이전트의 "develop 문서" 용어)을 소급 수정하지 않는다.
- Acceptance (오프라인 pytest): 스캔 범위에서 `docs/sdd/design/`, `docs/sdd/context/` 경로 문자열이 0건(단, 예외 두 가지: kompound 코어 docstring의 과거 arch 문서 인용은 `hooks/lib/kompound_snapshot/` 범위 제외, 구 라벨 호환용 `hooks/enforcement/stop-pipeline.py:217-227`의 `has_arch`/`has_ui`/`has_api`/`has_context`는 유지하므로 검사 제외). `skills/sdd-taskrunner/assets/templates/task-document.md`에 증분 빌드·테스트 실행 명령 칸이 없고 `테스트 스코프`가 있음. `tests/test_kompound_snapshot_*.py` 전체가 수정 없이 통과. `hooks/enforcement/phase-gate.sh`에 `DESIGN_DIR`, `HAS_ARCH`, `architecture 설계 문서`, `e2e-config` 문자열이 없고 `CONTEXT_DIR` 참조가 없음(SDD 미시작 판정은 `SPEC_DIR` 기준). `agents/webapp-architect.md`, `agents/flutter-architect.md`, `agents/native-architect.md`에 `ui-designer`, `api-designer` 문자열이 없음. `agents/sdd-blocker-checker.md`에 `ui-designer`가 없음. `agents/sdd-react-specialist.md`에 `DESIGN.md`가 없음. 구현 시 확인 항목(수정 여부 판단용): `hooks/enforcement/lib/constants.sh` 25행, `hooks/enforcement/lib/state-reader.sh` 53-58행의 e2e 설정 읽기 호출처가 휴면인지 확인해 결과 문서에 기록.

### F15: 비기능 — 버전, 크기, 검증, 승인 기록

- THE SYSTEM SHALL `.claude-plugin/plugin.json`과 `marketplace.json`의 버전을 모두 `0.15.0`으로 맞춘다.
- THE SYSTEM SHALL `skills/sdd/SKILL.md` 줄 수를 671 이하로 유지한다.
- THE SYSTEM SHALL 오프라인 테스트에서 네트워크·LLM을 호출하지 않고, 결정적 코드(라벨·directive·게이트)는 stdlib-only를 유지하며 조사·질문·요약·yes 판정은 SKILL/agent 프롬프트에 둔다.
- THE SYSTEM SHALL `stop-pipeline.py` 변경이 사용자 명시 승인(2026-10-19) 범위 안임을 커밋 메시지에 남긴다.
- Acceptance (오프라인 pytest): 두 JSON 파일의 `version`이 모두 `"0.15.0"`. `skills/sdd/SKILL.md` 줄 수 ≤ 671. Wave 1 종료 시와 Wave 2 종료 시 각각 `tests/` 전체 통과.

## 설계 결정

- D1. 인터뷰는 sdd 리드가 직접, 조사는 `Explore` 서브에이전트로(A2). 제로베이스도 동일 흐름. 사용자 확정.
- D2. 사용자 승인은 2회(Phase 1 spec, Phase 3 plan+tasks). Phase 번호는 유지해 Phase 4 참조 대량 수정을 피한다. Phase 2는 조건부 아키텍처 자리다. 사용자 확정.
- D3. 한 사이클로 진행하고 회귀 격리는 Wave 순서로 한다(Wave 1 = Phase 1, Wave 2 = Phase 2·3과 공통). 각 Wave 테스트 통과 후 다음 Wave. 사용자 확정.
- D4. code-mapper 걸림돌은 섹션 7이 아니라 "요구사항이 주어졌을 때만 붙는 별도 블록"이다(H29 불변량 보호). 코드맵 원본은 저장하지 않고 spec-writer가 요약·근거를 spec "코드 조사"에 기록한다. 사용자 확정.
- D5. 인터뷰 대기는 기존 `waiting_for_user` 메커니즘을 재사용한다. 라벨은 인터뷰 내내 `PHASE1_INTERVIEW_START`이고 질문 시점에 `waiting_for_user=true, type='interview'`, 응답 시 false로 되돌린다. 근거: H5, H6, H7(분기 소비 코드 없음). 새 훅 로직 없음.
- D6. 요약 승인 예외는 자연어 승인 표 바로 아래 한 줄로만 둔다. 기존 표는 다른 게이트용으로 유지한다. 사용자 확정.
- D7. 구 라벨은 모두 `DIRECTIVES` 별칭으로 남긴다. `PHASE1_UX_RESEARCH_DONE`는 새 라벨과 같은 문자열, 구 PHASE2 8개는 하나의 공통 호환 문자열(`PHASE3_PLAN_START`로 진행)을 쓴다. 이유: 구 directive를 그대로 두면 삭제된 에이전트를 호출하고(H2) 삭제하면 pipeline이 조용히 풀린다(H5). 구 PHASE2 라벨 실측 8개는 전부 별칭 대상이다. 구 PHASE2 별칭은 공통 directive "PHASE3_PLAN_START로 진행"을 쓰며, UI/API 승인 대기 중이던 구 pipeline이 그 승인을 건너뛰는 것을 허용한다(확정).
- D8. 새 Phase 2 라벨은 `PHASE2_ARCH_START` → `PHASE2_ARCH_DONE`, 또는 `PHASE2_ARCH_SKIP`이다. 둘 다 이어서 `PHASE3_PLAN_START`다. 아키텍처 판단은 리드가 spec 설계 결정을 보고 한다. `PHASE2_ARCH_DONE`/`SKIP`에는 `has_*` 파일 검사를 두지 않는다(문서가 spec 하나뿐이고 이미 `PHASE1_SPEC_DRAFT`에서 검증됨).
- D9. Phase 3 라벨은 `PHASE3_PLAN_START`(worktree 생성) → `PHASE3_WORKTREE_CREATED`(신규, `has_worktree` 검사, taskmaster tasks 모드 + 구현 계획) → `PHASE3_TASKMASTER_DONE` → `PHASE3_DAG_CONSTRUCTED` → `PHASE3_USER_APPROVED`다. 뒤 세 라벨의 키·directive는 유지한다. 신규 라벨 하나만 추가하는 이유: worktree 생성 완료를 파일 검사로 확인해 구현 계획 작성이 worktree 안에서 이뤄지게 하려는 것이다(`PHASE2_WORKTREE_CREATED`가 하던 역할의 이전). Phase 3 산출물(task, STATE)은 worktree에 쓰므로 `has_tasks`·`has_orchestrator_state`는 `worktree_path` 기준으로 본다(F10).
- D10. `init_pipeline`은 두 번째 인자를 받아 무시한다(구 호출 호환). 새 `pipeline.json`에 `mode`를 쓰지 않는다. `stop-pipeline.py:352`의 `mode` 읽기는 구 pipeline 호환으로 남긴다. 이유: 호출자(`sdd` SKILL의 구 호출형, 사용자 스크립트)를 깨지 않고 설계 모드 개념만 제거하는 최소 변경이다.
- D11. 한 문서의 섹션 소유권: spec-writer(목표~설계 결정 초안, 미결 질문), architect(설계 결정 보강, 조건부), taskmaster(`## 구현 계획`). 각 에이전트는 자기 섹션 외를 수정하지 않는다(R11).
- D12. 빌드 프로파일은 오케스트레이터가 Phase 4 진입 시 확보한다. STATE에 이미 있으면 재확보하지 않는다. 프로파일 스키마와 3원칙은 유지(F12).
- D13. E2E는 설계 단계에서 만들지 않고 수동 시나리오(result 문서) → 개발자 확인 → 요청 시 E2E 작성으로 바꾼다. `e2e-gate.sh`는 휴면(F13).
- D14. kompound 영향은 코드 조사로 확인했고 수정하지 않는다(I1, R7).
- D15. 템플릿 본문은 `skills/sdd/references/spec-template.md`, SKILL.md는 참조 한 줄(줄 수 상한 보호).
- D16. `skills/sdd/HANDOFF.md`, `docs/multi-agent-plan.md`, 엔지니어 에이전트의 "develop 문서" 용어, `skills/harness/SKILL.md`의 "spec/develop/task" 서술은 과거 용어이며 이번 변경과 직접 관계가 없어 수정하지 않는다.
- D17. 오케스트레이터 frontmatter `allowed-tools`에 `Skill`을 추가한다. 근거: 현재 값 `Bash Read Write Edit Glob Grep Agent`에 `Skill`이 없어 `/build-notes` 호출이 불가하다(리드 실측, U4/R9 해소).
- D18. `PHASE3_WORKTREE_CREATED` 진입 시 승인된 spec을 worktree의 같은 경로로 이동한다(복사 아님). 메인 체크아웃의 spec은 미커밋 파일이므로 이동 후 정본은 worktree 하나다. worktree에 같은 경로 파일이 이미 있으면 `cmp`로 동일할 때만 메인 사본을 삭제하고, 다르면 사용자에게 보고한다(F10). 조건부 Phase 2 architect는 worktree 생성 전이므로 메인 체크아웃의 spec을 보강한다. 근거: R10, H3. 이로써 정본이 둘로 갈라지지 않는다.

- D19. `skills/sdd/SKILL.md` ≤ 671 예산(대략치). 감소: Phase 2 본문(약 267-375행) ~109줄, arch 템플릿(약 376-424행) ~49줄, spec 템플릿 본문 → references 이동 ~35줄, 합계 약 -190줄. 증가: Phase 1 인터뷰·grill/why 디스패치 ~50줄, 조건부 아키텍처 ~20줄, Phase 3 worktree·계획 ~40줄, Phase 4 빌드 명령 확보 ~20줄, 기타(승인 예외 한 줄, 상태머신·표 갱신) ~15줄, 합계 약 +145줄. 순감 약 -45줄로 상한 내에 들어간다. 실제 줄 수는 F15 테스트가 단정한다. 위 수치는 추정치이므로 구현 중 `wc -l`로 실측하며 조정한다.

## 구현 계획

작성: sdd-taskmaster(Phase 3). task 문서: `docs/sdd/task/sdd-phase1-code-context/2026-10-19-T-{N}-*.md` (13개). 이 절 외 섹션은 수정하지 않았다(D11).

### Wave 순서와 태스크 의존

| Wave | 태스크 | 의존 | 비고 |
|------|--------|------|------|
| 1 | T-1 why 스킬 / T-2 grill + code-mapper 보강 / T-3 spec-writer + spec 템플릿 / T-4 stop-pipeline Phase 1 라벨 + init 초기 라벨 | 없음(서로 병렬, 파일 소유권 분리) | |
| 1 | T-5 `skills/sdd/SKILL.md` Phase 1 | T-1, T-2, T-3, T-4 | Wave 1 종료 게이트: `tests/` 전체 통과 |
| 2 | T-6 architect 3종 + 에이전트 4종 삭제 / T-7 stop-pipeline Phase 2·3 / T-8 pipeline-utils mode 폐지 + phase-gate / T-9 taskmaster·taskrunner / T-10 compliance·test-automator·blocker·react / T-11 오케스트레이터 | T-5(= Wave 1 게이트), T-7·T-8은 T-4에도 의존 | 병렬 가능, 소유 파일 분리 |
| 2 | T-12 `skills/sdd/SKILL.md` Phase 2~4·정책 | T-5, T-6, T-7, T-9, T-11 | |
| 2 | T-13 README·CLAUDE.md·버전 0.15.0·전체 정적 게이트 | T-6~T-12 | Wave 2 종료 게이트: `tests/` 전체 통과 |

공유 파일 소유권(순차 의존으로 직렬화):
- `skills/sdd/SKILL.md`: T-5(Phase 1) → T-12(Phase 2~4). 
- `hooks/enforcement/stop-pipeline.py`, `tests/test_stop_pipeline_characterization.py`: T-4 → T-7. `tests/test_sdd_pipeline_labels.py`: T-4 → T-7. `tests/test_stop_pipeline_kompound_gate.py`: T-4 단독.
- `hooks/enforcement/lib/pipeline-utils.sh`, `tests/test_sdd_pipeline_init.py`: T-4 → T-8.
- 전 태스크가 서로 다른 파일을 소유하며 같은 Wave 병렬 태스크 간 겹침이 없다. 전체 스캔 테스트는 T-13이 소유하고, 위반이 타 소유 파일에서 나오면 해당 소유 태스크로 되돌린다.

protected 파일: `stop-pipeline.py`(T-4, T-7)와 `phase-gate.sh`(T-8)는 사용자 승인 완료(spec 승인 기록, 2026-10-19). 승인 범위 밖은 Ask first.

### 위험 (Risk 절 참조)

- R1/R2(인터뷰 대기·yes 규칙): T-4(훅 측 `waiting_for_user`), T-5(SKILL 측 호출 순서·예외 한 줄).
- R3/D7(구 pipeline 승인 건너뜀): T-7 별칭 directive 동일성 테스트.
- R4(승인 범위 이탈): T-4·T-7·T-8 비고에 범위 명시.
- R6(Explore 쓰기 금지는 프롬프트 규칙): T-1 정적 테스트는 지침 존재만 보장.
- R7/R12(kompound 영향, STATE 경로 소비자): 수정하지 않고 T-13이 결과 문서용 기록만 남긴다.
- R8(phase-gate 오경고): T-8.
- R11(섹션 소유권): T-3(spec-writer), T-6(architect), T-9(taskmaster)가 각 지침에 명시.
- 줄 수 ≤ 671(D19): T-5, T-12, T-13이 각각 단정.

### F1~F15 Acceptance → 태스크 매핑

| F | 담당 태스크 | 비고 |
|---|-----------|------|
| F1 | T-1 | 수동 Acceptance는 결과 문서에 수행 여부 기록 |
| F2 | T-2 | 수동 Acceptance 동일 |
| F3 | T-2 | `hooks/lib/code_mapper/` 무변경 기록 |
| F4 | T-5 (+T-3, T-4, T-13) | `ux-researcher` 0건: 선행 T-3/T-4, 전수 확인 T-13 |
| F5 | T-3 | |
| F6 | T-3(템플릿), T-5(SKILL 참조), T-13(경로 0건) | |
| F7 | T-4 | 별칭·초기 라벨·기존 테스트 갱신 |
| F8 | T-4(훅), T-5(SKILL) | 수동 Acceptance 기록 |
| F9 | T-6(agents), T-7(DIRECTIVES), T-12(SKILL) | |
| F10 | T-7(코드), T-9(taskmaster), T-12(SKILL Phase 3) | |
| F11 | T-8(셸), T-7·T-9·T-10·T-12(문구), T-13(스캔) | `mode` 읽기 호환은 코드 변경 없음 |
| F12 | T-11, T-12 | T-13이 스캔 0건 단정 |
| F13 | T-10, T-11, T-12, T-3(템플릿 문구) | `e2e-gate.sh` 무변경 T-8/T-13 |
| F14 | T-6~T-13 각 소유 파일 | kompound 코어·테스트 무수정 T-13 |
| F15 | T-13(버전·줄 수), Wave 게이트 T-5/T-13 | 커밋 메시지에 승인 기록 |

### 태스크별 테스트 스코프

실행 형식은 `<PY> -m pytest <스코프> -q` (CLAUDE.md "빌드 / 테스트" 절의 확정 절차, bq light lane).

| 태스크 | 스코프 |
|--------|--------|
| T-1 | `tests/test_why_skill.py` |
| T-2 | `tests/test_grill_skill.py`, `tests/test_code_mapper_blockers.py`, `tests/test_code_mapper_core.py` |
| T-3 | `tests/test_sdd_spec_writer.py` |
| T-4 | `tests/test_stop_pipeline_characterization.py`, `tests/test_stop_pipeline_kompound_gate.py`, `tests/test_sdd_pipeline_labels.py`, `tests/test_sdd_pipeline_init.py` |
| T-5 | `tests/test_sdd_phase1_skill.py` + Wave 1 게이트 `tests/` 전체 |
| T-6 | `tests/test_sdd_phase2_agents.py` |
| T-7 | characterization, kompound_gate, `tests/test_sdd_pipeline_labels.py`, `tests/test_sdd_pipeline_phase3.py` |
| T-8 | `tests/test_sdd_pipeline_init.py`, `tests/test_phase_gate_single_doc.py`, `tests/test_enforcement_hook_false_positives.py`, `tests/test_hooks_json_contract.py` |
| T-9 | `tests/test_sdd_task_docs.py` |
| T-10 | `tests/test_sdd_agent_consumers.py` |
| T-11 | `tests/test_sdd_orchestrator_docs.py` |
| T-12 | `tests/test_sdd_phase234_skill.py`, `tests/test_sdd_phase1_skill.py` |
| T-13 | `tests/test_sdd_static_docs.py` + Wave 2 게이트 `tests/` 전체 |

## 테스트 전략

- 테스트 seam: `stop_pipeline.decide()`, `DIRECTIVES`, `label_prerequisite_met`는 `stop_pipeline` fixture(importlib 로드)로 임포트 가능한 seam이다. `pipeline-utils.sh`는 임시 디렉터리 + `CLAUDE_PROJECT_DIR`로 `init_pipeline`/`show_pipeline`을 실행해 `pipeline.json` 결과를 검증한다(H9). SKILL/agent/README는 파일 읽기 기반 정적 검사(frontmatter, 키워드, 금지 문자열, 줄 수)로 검증한다. 모듈 전역 mock/patch는 쓰지 않는다.
- 새 테스트 파일(제안 이름): `tests/test_sdd_pipeline_labels.py`(라벨 체인, 별칭, 닫힌 그래프), `tests/test_sdd_pipeline_init.py`(`init_pipeline` 초기 라벨·`mode` 처리), `tests/test_sdd_static_docs.py`(frontmatter, 금지 문자열, 삭제 에이전트 참조 0건, 줄 수, 버전, 정규식 샘플).
- 라벨 그래프 닫힘 테스트(W5): (a) 새 체인의 각 directive가 후속 라벨명을 포함, (b) directive 본문에 등장하는 `PHASE\d_[A-Z_]+` 토큰이 모두 `DIRECTIVES` 키로 존재(PHASE4 태스크 라벨 `PHASE4_TASK_{N}_*` 템플릿 제외), (c) 별칭 directive 동일성.
- 기존 테스트 갱신: `test_stop_pipeline_characterization.py`(`_ALWAYS_MET_LABELS`, `_KNOWN_NON_TERMINAL_LABELS`, 구 라벨 케이스는 유지하고 새 라벨 추가), `test_stop_pipeline_kompound_gate.py:417`. `_mk_state`의 `"mode": "SIMPLE"`은 구 pipeline 호환 입력으로 남긴다. 기대값 약화 금지.
- Wave 게이트: Wave 1 끝(F1~F8 + 관련 테스트) → `tests/` 전체 통과 확인 → Wave 2. Wave 2 끝 → 전체 통과.
- 정적 테스트 스캔 범위: `skills/`, `agents/`, `hooks/`(단 `hooks/lib/kompound_snapshot/` docstring 제외), `.claude-plugin/`, `README.md`, `CLAUDE.md`. 제외: `docs/sdd/**`, `.harness/**`, `tests/**`, `docs/` 루트의 과거 문서.
- 수동 검증(오프라인 불가): `/grill` 번호+추천 답 라운드와 "좋아 보여" 비승인, `/why` 출력 구조, 인터뷰 대기 중 Stop 훅 거동, Phase 3 worktree 생성, `/build-notes` 폴백 경로. 결과 문서에 수행 여부를 적는다.
- 오프라인 테스트는 네트워크·LLM을 호출하지 않는다. 라이브 eval은 만들지 않는다.

## 적용 규칙

- `CLAUDE.md`(moon-harness): 결정↔판단 분리(라벨·directive·게이트는 stdlib-only 결정적 코드, 질문·조사·yes 판정은 프롬프트), protected set(`stop-pipeline.py`, 게이트 스크립트), 2티어 격리(플러그인 skills/agents/hooks = 하네스 티어 변경이므로 사람 승인 근거를 커밋 메시지에 남김), 버전 두 파일 동기화, 브랜치 prefix `feature/`, 병렬 작업 시 소유 파일만 명시적 `git add`와 브랜치 전환 금지.
- `docs/lessons-learned.md`: 문서의 복사-실행 명령에 인터프리터 경로·`PATH=` prefix를 적지 않고 확정 절차를 적는다.
- `.harness/LEARNING.md` 2026-08-06 "커서 마커 형식 불일치": 문서가 적는 상태값·라벨 문자열이 소비 코드를 통과하는지 테스트로 고정한다(F7, F9, F10).
- ANTI_SLOP(로드된 전역 규칙) 중 이번 변경에 걸리는 것: 새 Python/테스트 코드는 타입이 알려진 값을 넓히지 않고, 모듈 전역 mock/patch 대신 fixture·`tmp_path`·환경변수 주입을 쓰고, 문자열 검사는 경계에서 한 번 하며, filter 후 map 같은 이중 패스를 피한다. 기존 코드는 쓸어 고치지 않고 변경 줄만 맞춘다. bash 변경은 기존 스타일을 따른다.
- 표기: spec은 구 마커 대신 "미결 질문"을 쓴다. 사용자 원문은 변형하지 않는다.

## 빌드/테스트 명령

- `CLAUDE.md`의 "빌드 / 테스트" 절을 따른다. 형식은 `<PY> -m pytest tests/ -q`이며 `<PY>`는 CLAUDE.md의 확정 절차로 정한다. 인터프리터 경로를 하드코딩하지 않는다.
- Wave 1 범위 테스트: `<PY> -m pytest tests/test_stop_pipeline_characterization.py tests/test_stop_pipeline_kompound_gate.py tests/test_code_mapper_core.py tests/test_sdd_pipeline_labels.py tests/test_sdd_pipeline_init.py tests/test_sdd_static_docs.py -q`.
- Wave 2 종료: `<PY> -m pytest tests/ -q` 전체.
- 사용자 전역 규칙상 pytest는 light lane이다: `bq submit --wait --lane light -- <명령>`.

## Boundaries

Always:
- 구 라벨(`PHASE1_UX_RESEARCH_DONE` + 구 PHASE2 8개)을 `DIRECTIVES` 별칭으로 유지한다.
- 변경 전 `Grep`으로 삭제 대상 에이전트명, 구 라벨명, `design/`, `context/` 잔존 참조를 확인한다(`docs/sdd/**` 제외).
- `stop-pipeline.py`/`pipeline-utils.sh` 변경 후 전체 `tests/`를 돌린다.
- Wave 1 통과 확인 후에만 Wave 2에 착수한다.
- 병렬 에이전트는 소유 파일만 명시적으로 `git add`한다.
- 하네스 티어 변경은 이 spec이 승인 범위의 근거임을 커밋 메시지에 남긴다. `stop-pipeline.py` 변경은 "사용자 명시 승인 2026-10-19"를 커밋 메시지에도 적는다.

Ask first:
- `stop-pipeline.py`에서 승인 범위(DIRECTIVES 문자열·별칭 키·신규 라벨 키, `label_prerequisite_met`의 `PHASE3_WORKTREE_CREATED` 항목 추가, `has_tasks`·`has_orchestrator_state`의 `worktree_path` 기준 변경) 밖을 바꿔야 할 때: Step 순서, 서킷 브레이커, `decide()` 흐름, kompound 게이트, 그 외 기존 `checks` 항목 수정. 승인 범위 `stop-pipeline.py`와 `phase-gate.sh`(F14의 블록 제거)는 둘 다 protected 게이트 스크립트이며 사용자 승인은 spec 승인 게이트에서 받는다.
- `pipeline-utils.sh`에서 초기 라벨, `mode` 처리, 사용 주석, `show_pipeline`의 `mode` 출력 밖을 바꿔야 할 때.
- `phase-gate.sh`(F14 블록 제거 밖), `e2e-gate.sh`, `hooks.json`, kompound-snapshot 코어(`scan.py` 등)를 바꿔야 할 때.
- code-mapper 결정적 코어나 섹션 1~6을 바꿔야 할 때.
- 삭제 4종 외 에이전트를 삭제하거나 새 라벨을 더 추가해야 할 때.

Never:
- self-improve, pr-converge, harness-improvement-critic을 수정하지 않는다(protected, 범위 밖).
- 사용자에게 환경에서 알 수 있는 사실을 묻지 않는다.
- code-mapper 산출물을 파일로 저장하지 않는다.
- 플러그인 파일에 사용자 홈 경로를 하드코딩하지 않고 인터프리터 경로/`PATH=` prefix를 문서에 적지 않는다.
- `build-notes`를 플러그인으로 이관하지 않는다.
- 완료된 사이클 산출물(`docs/sdd/**` 과거 문서)을 소급 수정하지 않는다.
- 공유 worktree에서 `git add -A`/`.`를 쓰거나 브랜치를 전환하지 않는다.
- TDD 모드 FULL(`[TDD == FULL]`, `tdd-gate.sh`)을 설계 모드로 오인해 변경하지 않는다.

`stop-pipeline.py`는 protected 게이트 스크립트이며 사용자가 이번 변경(2026-10-19)을 명시적으로 승인했다. `phase-gate.sh`도 protected 게이트 스크립트이며 F14 범위의 변경은 spec 승인 게이트에서 사용자 승인을 받는다.

## 범위 밖

- floor guard 훅.
- self-improve 변경(protected set 포함).
- 리뷰 오탐 필터.
- pr-converge 변경.
- 완료된 사이클 산출물 소급 수정.
- `build-notes`의 플러그인 이관.
- idea-workshop 관련 일체(b3a7ff8로 완료).
- code-mapper의 시각화, AST 엔진, 영속화 등 기존 비목표.
- why의 Cursor 전용 동작 이식과 서비스별 playbook 복제.
- `phase-gate.sh`의 선재 `case` 분기 순서 결함(H11; F14 블록 제거와 별개), 엔지니어 에이전트의 "develop 문서" 용어 정리.
- STATE 경로 소비자의 worktree 인식(R12: `stop-pipeline.py:449-451`, `constants.sh:30` → `branch-gate.sh`, `worktree-add-gate.sh`, `escalation-tracker.sh`, `state-reader.sh`, `phase-gate.sh:26`).
- `has_spec`/`has_blocker_pass`가 feature를 구분하지 않고 `docs/sdd/spec/*.md` 전체를 보는 선재 동작.

## 미결 질문

없음. (Q1은 D18, Q2·Q3은 D7, U4/R9는 D17로 해소됐다.)

---
## 승인 기록
- 2026-10-19 blocker-check: 3회 실시, 마지막 잔여 1건(F12 스캔 범위)은 리드가 수정 후 rg 실측으로 확인하기로 사용자 합의.
- 2026-10-19 사용자 Phase 1 spec 승인("진행해줘"). protected 파일 변경 승인 포함: hooks/enforcement/stop-pipeline.py, hooks/enforcement/phase-gate.sh.
- 아키텍처 변경 없음 → PHASE2_ARCH_SKIP.

BLOCKER_PASS
