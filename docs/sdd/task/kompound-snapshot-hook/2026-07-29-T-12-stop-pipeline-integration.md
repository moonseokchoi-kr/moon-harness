# T-12: F1 — T1 정상 경로 강제 (`stop-pipeline.py` 수정 + SKILL.md 문서화)

## ⚠️ PROTECTED SET — 사람 승인 필요 (F15)
`hooks/enforcement/stop-pipeline.py`는 `hooks/lib/self_improve/guard.py`의 `PROTECTED_SET`이 보호하는 `hooks/enforcement/` 디렉토리 안에 있다. CLAUDE.md: "게이트 스크립트는 자동 생성/수정 금지(사람만)". **이 사이클은 사용자가 이번 대화에서 명시적으로 지시하여 protected-set 승인 조건을 충족했다**(spec F15, arch §10.1). result 문서와 PR 설명에 "하네스 티어 / 사람 승인 완료" 표기가 있어야 머지 가능하다. 자동 승격 경로(self-improve)로는 이 변경을 만들 수 없다.

**이 태스크는 T-1(F17 회귀 안전망)이 GREEN으로 확인된 뒤에만 시작한다.** T-1은 필요조건이지 충분조건이 아니다 — 위 사람 승인 요건은 T-1로 대체되지 않는다.

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F1(전문 — 삽입 지점·강제 수준·Acceptance 전부), F15(2티어 판정)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §5.1(F1 — T1 통합 전체), §5.1.1(C1/C2/C3 실측 제약 — "라벨 체인에 끼워 넣지 않는다"는 결론의 근거), §5.1.2(확정 사항 표), §5.1.3(4조건 AND 판정 + 판정 결과 표 + T1의 (i)/(ii) 정책), §5.1.4(서킷브레이커 비공유, A-1), §5.1.5(SKILL.md 문서화 위치), §10.1(protected set)

## 구현자
sdd-python-engineer

## 테스트 타입
단위(`decide()` 직접 — importlib) + 통합(`stop-pipeline.sh` 서브프로세스 1세트, `PYTHONPATH` 없이도 부트스트랩 성립 확인)

## 완료 조건
- [ ] **삽입 위치**: `decide()`(L334) **Step 0(context limit) 직후**에 pipeline.json과 독립적인 완료 게이트를 신설한다(C1/C2/C3 근거로 라벨 체인 연장은 채택하지 않음). 기존 Step 1~9는 이 게이트가 무장되지 않은 모든 입력에서 **완전히 동일하게 동작**해야 한다(T-1 회귀 안전망으로 이 불변성이 검증됨).
- [ ] **의사 라벨**: `DIRECTIVES["PHASE4_KOMPOUND_SNAPSHOT_PENDING"]` 키를 신규 추가한다. 이 키는 선형 라벨 체인의 원소가 **아니며** `decide()`가 `current_label`로 조회하는 방식이 아니다 — 완료 게이트가 directive 문자열을 조회하는 용도로만 쓴다. 기존 16개 라벨의 `DIRECTIVES` 매핑은 무변경(T-1 스코프 2가 이를 고정).
- [ ] **코어 import 부트스트랩(필수)**: plugin root = `CLAUDE_PLUGIN_ROOT`(있으면 `_winify_path` 통과) 없으면 `Path(__file__).resolve().parents[2]`. `sys.path`에 없으면 `sys.path.insert(0, str(plugin_root))`. **import는 완료 게이트 함수 내부에서 지연 수행**(모듈 최상위 import 금지) — 무장되지 않은 대다수 호출에서 import 비용 0, import 실패가 기존 파이프라인 전체를 무력화하지 않도록.
- [ ] **판정 4조건 AND**: ① 무장(STATE 서명 변화, T-7 `runtime_state`의 baseline 비교 함수 호출) ② STATE 신선도(`state_max_age_hours` 이내, 보조 조건) ③ 상태==COMPLETED(D1: Step 4-2 직후) ④ 코어 `check`(부작용 없음) 결과 `pending≥1`(T-11 cli의 `check` 서브커맨드를 in-process 호출).
- [ ] **판정 결과 표(arch §5.1.3)를 그대로 구현**: 무장 안 됨/오래됨/상태≠COMPLETED → Step 1로 진행(baseline만 갱신) / config 미해석 → `{"continue": true}` + `SKIPPED_UNCONFIGURED` + 안내 1회 / `pending==0` → `{"continue": true}` + `DONE` / **직전 상태 `CATALOG_PENDING`** → `{"continue": true}`(DONE과 동일 취급, `blocks` 미증가) / `pending≥1, blocks<3` → block + directive + `PENDING`, `blocks+=1` / `pending≥1, blocks==3` → 마지막 1회 block("3회 안내했으나 미완 — T2가 재차 막는다") 후 `GIVEN_UP` / 런타임 상태 write 실패 → block 안 함(`{"continue": true}` + 경고) / 코어 예외·import 실패 → `{"continue": true}` + `FAILED`(블록 예산 미소모).
- [ ] **서킷브레이커 비연동**: `increment_breaker(state)`를 호출하지 않는다. 우리 게이트는 `pipeline.json`을 읽지도 쓰지도 않는다(워크트리 경로 힌트로만 read-only 참고 가능). 자체 `KOMPOUND_MAX_BLOCKS=3` 카운터만 사용(T-7 `runtime_state` 구현 재사용).
- [ ] **directive 문구**: `str.format` 금지(기존 directive들이 `{YYYY-MM-DD}` 등 리터럴 중괄호를 포함해 `KeyError` 위험) — 리터럴 토큰(`@@CLI@@`, `@@SCOPE@@`) + `str.replace` 사용. 문구는 ① 지금 박제 실행 명령(절대경로 포함) ② 성공/실패 보고 지시 ③ self-improve(Step 5)보다 먼저 끝내라는 지시 3요소.
- [ ] spec F1 Acceptance 전부 충족:
  - [ ] `stop-pipeline.py`에 4-2 완료 시점 대응 라벨/상태 분기 + 박제 directive 문자열 존재, 이를 커버하는 오프라인 pytest가 `tests/`에 존재.
  - [ ] 박제 미완(`pending≥1`)에서 Stop 훅이 `{"decision":"block"}` + directive 반환, 박제 완료(`pending==0`) 또는 kompound 미설정 시 즉시 통과하는 대칭 테스트 존재.
  - [ ] 동일 사이클 2회 실행 시 두 번째 실행이 "이미 박제됨"으로 무동작 판정되는 테스트 존재.
  - [ ] kompound 경로가 F16 어디서도 해석되지 않는 환경에서 T1이 "무동작 통과"로 종료(사이클 완료를 영구 차단하지 않음)하는 테스트 존재.
  - [ ] 카탈로그 갱신만 실패하고 raw 복사는 성공한 상태에서, 다음 Stop 훅 발화가 재차 차단하지 않고 블록 예산도 소모하지 않음을 **차단 전후 예산 값 비교**로 단정하는 테스트 존재.
- [ ] `skills/sdd-orchestrator/SKILL.md` Step 4의 2번(`ORCHESTRATOR_STATE.md`=COMPLETED)과 3번(push+pr-converge) **사이**에 박제 스텝을 문서화한다. 그 텍스트가 Step 5(self-improve) 텍스트보다 **앞선 줄 번호**에 위치해야 한다(spec F1 Acceptance의 "줄 번호" 검증 대상).
- [ ] T-1의 회귀 안전망(`tests/test_stop_pipeline_characterization.py`, `tests/test_hooks_json_contract.py`)이 이 수정 **후에도** 전부 GREEN이다(부트스트랩 무해성 케이스 포함).
- [ ] 전체 스위트 회귀 없음(기존 533 + T-1 신규분 + 이 태스크 신규분 전부 GREEN).

## 의존 태스크
T-1(F17 회귀 안전망 GREEN — 필수 선행), T-11(cli.py의 `check` 서브커맨드), T-7(runtime_state — 상태 판정 함수 전체)

## 예상 변경 파일
- `hooks/enforcement/stop-pipeline.py` — 수정(protected)
- `skills/sdd-orchestrator/SKILL.md` — 수정(Step 4 문서화, non-protected)
- `tests/test_stop_pipeline_kompound_gate.py` — 신규(F1 신규 분기 전용 테스트 — T-1의 characterization 파일과는 별개 파일로 분리해 "새 기능 테스트"와 "회귀 고정"의 성격을 섞지 않는다)

## Steps
- [ ] `stop-pipeline.py`에 plugin root 부트스트랩 코드(모듈 최상위, `sys.path` 부작용만) 추가
- [ ] `decide()` Step 0 직후에 완료 게이트 함수 호출 삽입 — 게이트 함수 내부에서 `hooks.lib.kompound_snapshot.{config,runtime_state,cli}` 지연 import
- [ ] `DIRECTIVES["PHASE4_KOMPOUND_SNAPSHOT_PENDING"]` directive 문자열 추가(`str.replace` 토큰 방식)
- [ ] 완료 게이트 함수 구현 — 4조건 AND 판정 → T-7 `runtime_state` 판정 함수 호출 → 판정 결과 표에 따라 반환값 조립
- [ ] `skills/sdd-orchestrator/SKILL.md` Step 4에 박제 스텝 삽입(2번과 3번 사이, Step 5보다 앞선 줄 번호)
- [ ] `tests/test_stop_pipeline_kompound_gate.py` 작성 — spec F1 Acceptance 5개 항목 전부 커버(차단/통과 대칭, 2회 실행 멱등, kompound 미설정 무동작, 카탈로그 지연 시 예산 미소모 전후 비교)
- [ ] T-1의 회귀 안전망 재실행 — GREEN 확인(부트스트랩 무해성 케이스 포함)
- [ ] `pytest tests/ -q` 전체 회귀 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_stop_pipeline_kompound_gate.py -q
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_stop_pipeline_characterization.py tests/test_hooks_json_contract.py -q   # T-1 회귀 재확인
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q
```

## 테스트 스코프
`tests/test_stop_pipeline_kompound_gate.py`(신규 분기) + `tests/test_stop_pipeline_characterization.py`(회귀 재확인) — 또는 `pytest tests/ -k "stop_pipeline"`
