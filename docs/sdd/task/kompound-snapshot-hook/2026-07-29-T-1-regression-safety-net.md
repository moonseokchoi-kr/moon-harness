# T-1: F17 회귀 안전망 — stop-pipeline.py / hooks.json characterization test

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F17 (§전문), F1 Acceptance 마지막 항목("F17의 회귀 안전망이 GREEN으로 확인된 뒤에만 시작")
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §9.2 (F17 구조: 파일 배치·스코프→심볼 매핑·import 방식), §9.1 표의 "회귀 안전망 (F17)" 행

## 구현자
sdd-test-automator (**refactor 모드** — 회귀 안전망. tdd 모드가 아니다)

## 테스트 타입
단위 (characterization test) + 계약(정적) 검사. E2E 없음(UI 없음).

## 완료 조건
- [ ] `tests/test_stop_pipeline_characterization.py`가 존재하고 파일 상단에 "characterization test — 현재 동작 고정, 스펙 아님. 현재 존재하는 버그까지 함께 고정한다. 의도적 변경 시 이 파일을 함께 갱신한다." 취지의 주석이 있다.
- [ ] 동일 파일에 F17 스코프 외 항목(`is_stale` staleness · `check_session_match` 세션 매칭 · `atomic_write` 등)이 이번 사이클 대상이 아니라는 문서화 주석이 있다.
- [ ] **스코프 1 — 라벨 전이(`decide`, L334)**: 현재 16개 라벨 각각에 대해 `decide()`의 반환값(`{"continue": true}` vs `{"decision":"block","reason":...}`)이 입력(라벨·상태·`pipeline.json` 유무)별로 고정되어 있다. 특히 `PHASE4_WORKTREE_CREATED`(터미널, L371)이 항상 즉시 `{"continue": true}`를 반환함을 고정한다.
- [ ] **부트스트랩 무해성 케이스(스코프 1의 일부, §9.2)**: `sys.path.insert(0, <plugin root>)`가 모듈 최상위에 추가된 후에도(T-12에서 도입 예정) 기존 Step 0~9의 동작이 입력별로 완전히 동일함을 고정하는 케이스가 있다(수정 전엔 부트스트랩이 없으므로 "부트스트랩이 없는 현재 상태"를 기준값으로 잡고, 있어도/없어도 결과가 같은 입력들로 구성).
- [ ] **스코프 2 — `DIRECTIVES`(L63) 선택**: 기존 16개 라벨 각각의 매핑 **존재와 형태**를 단정한다(키 집합 동일성은 단정하지 않는다 — T-12가 `PHASE4_KOMPOUND_SNAPSHOT_PENDING` 키를 추가하므로). 단정 대상: ① 16개 라벨 각각에 대응하는 directive 존재 ② `DIRECTIVES["PHASE4_WORKTREE_CREATED"] is None` ③ 각 directive 문자열이 `"[SDD-PIPELINE]"`로 시작.
- [ ] **스코프 3 — `label_prerequisite_met`(L296)**: `has_spec`/`has_blocker_pass`/`has_worktree`/`has_arch`/`has_ui`/`has_api`/`has_context`(FULL/SIMPLE 분기)/`has_tasks`/`has_orchestrator_state`의 각 선행조건 판정(충족/미충족 양쪽)이 고정되어 있다. `checks`에 없는 라벨은 `(True, "")`을 반환함(L322)도 고정한다.
- [ ] **스코프 4 — 서킷브레이커**: `check_circuit_breaker`(L262, `CB_MAX_BLOCKS=20`/`CB_TTL_MINUTES=5` 기준 allow/reset 판정) · `increment_breaker`(L279) · `reset_breaker`(L286)의 상태 변형이 입력별로 고정되어 있다.
- [ ] **스코프 5 — `hooks/hooks.json` 유효성**: `tests/test_hooks_json_contract.py`가 존재하며, (a) 현재 `hooks.json`이 유효한 JSON이고 (b) `PreToolUse`>`matcher:"Bash"` 배열의 기존 5개 커맨드(`dangerous-command.sh`, `secret-detect.sh`, `branch-gate.sh`, `worktree-add-gate.sh`, `e2e-gate.sh`)가 정확히 이 순서로 존재함을 검증한다. 이 테스트는 **T-13(F14 hooks.json 등록) 이후에도 재실행되어 6개 항목(5개 보존 + 신규 게이트 1개 추가)으로 GREEN이어야 한다** — 즉 이 테스트는 "5개 보존"이 아니라 "기존 5개가 5개 그대로 부분집합으로 남아있고 신설 항목이 그 뒤에 추가되었는가"를 검증하도록 작성한다(T-13 이후를 향한 하위호환 단정).
- [ ] `stop-pipeline.py`를 **수정하기 전** 시점의 코드에 대해 `tests/test_stop_pipeline_characterization.py` + `tests/test_hooks_json_contract.py`가 전부 GREEN이다.
- [ ] 전체 스위트 실행 결과 기존 533개 테스트 중 실패 0(신규 테스트는 추가되되 기존 533개는 그대로 통과).
- [ ] import는 `importlib.util.spec_from_file_location("stop_pipeline", <path>)` 방식을 사용한다(`tests/test_self_improve_scripts.py:35-41`의 `_load()` 선례와 동일 패턴). 모듈 이름은 하이픈이 아닌 `stop_pipeline`(유효 식별자)을 쓴다.

## 의존 태스크
없음 (Wave 0, 최우선 선행)

**후속 관계 (역방향)**: T-12(F1, stop-pipeline.py 수정)와 T-13(F14, hooks.json 등록)은 **이 태스크가 GREEN으로 완료된 뒤에만** 시작한다. 이 두 태스크는 protected set이며 사람 승인이 추가로 필요하다(F15) — 이 안전망은 그 필요조건 중 하나(충분조건 아님)다.

## 예상 변경 파일
- `tests/test_stop_pipeline_characterization.py` — 신규, 스코프 1~4
- `tests/test_hooks_json_contract.py` — 신규, 스코프 5

## Steps
- [ ] `importlib.util.spec_from_file_location`으로 `hooks/enforcement/stop-pipeline.py`를 `stop_pipeline`이라는 모듈명으로 적재하는 로더 헬퍼 작성(`tests/test_self_improve_scripts.py`의 `_load()` 패턴 재사용/이식)
- [ ] `decide()`에 대해 `pipeline.json`을 `tmp_path`에 준비하고(`last_updated`를 항상 신선하게 유지 — `is_stale` 함정 회피) 16개 라벨 각각에 대한 입력·기대출력 표를 케이스로 작성
- [ ] `pipeline.json` 부재(C3, `/sdd-orchestrator` 직접 실행 케이스) 시 `decide()`가 `{"continue": true}`로 즉시 종료함을 고정하는 케이스 추가
- [ ] `DIRECTIVES` 딕셔너리에 대해 스코프 2가 요구하는 3개 성질(존재/형태, 터미널 `None`, `[SDD-PIPELINE]` 접두)을 단정하는 테스트 작성 — **키 집합 전체 동일성은 절대 단정하지 않는다**(브리틀 방지, §9.2)
- [ ] `label_prerequisite_met`의 각 `has_*` 검사군에 대해 충족/미충족 fixture(예: `docs/sdd/spec/*.md` 존재 여부)를 `tmp_path` 프로젝트 트리로 구성해 검증
- [ ] `check_circuit_breaker`/`increment_breaker`/`reset_breaker`에 대해 blocks 증가·TTL 만료 reset·`CB_MAX_BLOCKS` 초과 시 allow+reset 조합을 단정
- [ ] "부트스트랩 무해성" 케이스 — 현재(부트스트랩 없는) 코드 기준 스냅샷을 기준값으로 잡아두고, T-12 완료 후 동일 케이스가 여전히 동일 결과를 내는지 재확인할 수 있도록 케이스를 파라미터화
- [ ] `tests/test_hooks_json_contract.py` 작성 — JSON 파싱 성공 + `PreToolUse`>`Bash` 배열의 5개 기존 커맨드가 이 순서로 존재함을 단정(리스트 슬라이스 비교, 신규 항목이 뒤에 붙어도 통과하도록 "처음 5개가 이 값들"로 단정 — 정확히 5개라는 개수 단정은 피한다)
- [ ] 두 파일 상단에 characterization test 성격 주석 + 스코프 외 항목 문서화 주석 추가
- [ ] `PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_stop_pipeline_characterization.py tests/test_hooks_json_contract.py -v` GREEN 확인 후, 전체 스위트 재실행으로 기존 533개 무손상 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_stop_pipeline_characterization.py tests/test_hooks_json_contract.py -q
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q   # 기존 533 passed 회귀 확인 (신규분 추가 허용, 기존 실패 0)
```

## 테스트 스코프
`tests/test_stop_pipeline_characterization.py`(스코프 1~4) + `tests/test_hooks_json_contract.py`(스코프 5). 이 두 파일 자체가 안전망이므로 "이 태스크의 테스트"는 곧 "이 태스크의 산출물"이다 — 별도 구현 코드 없음(순수 회귀 고정).
