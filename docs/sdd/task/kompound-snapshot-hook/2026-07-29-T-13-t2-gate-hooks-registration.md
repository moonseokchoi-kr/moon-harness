# T-13: F2/F14 — T2 안전망 게이트 신규 + hooks.json 등록

## ⚠️ PROTECTED SET — 사람 승인 필요 (F15)
신규 게이트 스크립트(`hooks/enforcement/kompound-snapshot-gate.sh`)와 `hooks/hooks.json` 모두 CLAUDE.md의 protected set이다("게이트 스크립트는 자동 생성/수정 금지, 사람만"). **이 사이클은 사용자가 이번 대화에서 명시적으로 지시하여 승인 조건을 충족했다**(spec F15, arch §10.1). result 문서/PR 설명에 "하네스 티어 / 사람 승인 완료" 표기 필수.

**이 태스크는 T-1(F17 회귀 안전망) GREEN 확인 후에만 시작한다.**

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F2(전문), F14(전문)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §5.2(F2 전체), §5.2.1(확정 사항 — 스크립트명·등록 위치·차단 코드), §5.2.2(명령 파싱 — bash 프리필터 부분만, 코어 파싱은 T-6 완료됨), §5.2.3(5분기 제어 흐름 — bash가 소비하는 verdict/exit 매핑), §5.2.4(3축 원칙), §3.1(`kompound-snapshot-gate.sh`는 `worktree-add-gate.sh`와 동일 골격)

## 구현자
sdd-implementer (bash 게이트 — `worktree-add-gate.sh` 골격 준수)

## 테스트 타입
통합 (bash 서브프로세스 + stdin JSON — 기존 게이트 테스트 관례, arch §9.1 "T2 게이트 스크립트" 행)

## 완료 조건
- [ ] `hooks/enforcement/kompound-snapshot-gate.sh`가 `hooks/enforcement/worktree-add-gate.sh`와 **동일한 골격**을 따른다: `lib/constants.sh`·`lib/logging.sh` 소싱 → INPUT(`cat`) 파싱 → `tool_name` 확인(`!= Bash` → exit 0) → `command` 확인(빈 문자열 → exit 0) → 관련 명령만 처리(프리필터) → 판정 → `gate_block`/`gate_pass`.
- [ ] **bash 프리필터**(§5.2.2, 비용 상한 <5ms): `case "$COMMAND" in *worktree*remove*|*rm\ -r*|*rm\ -f*|*--recursive*) ;; *) exit 0 ;; esac` — 무관 명령은 python 미기동으로 즉시 통과.
- [ ] **코어 호출**: `python3 -m hooks.lib.kompound_snapshot gate --command "$COMMAND" --json`(T-11 cli.py의 `gate` 서브커맨드). 판정 로직을 bash에 복제하지 않는다.
- [ ] **5개 분기 제어 흐름을 정확히 구현**(arch §5.2.3):
  - `tool_name != Bash` → exit 0
  - COMMAND 프리필터 미통과 → exit 0 [분기5: 무관 명령 무개입]
  - python3/모듈 없음 → `gate_warn` + `gate_pass` + exit 0 [인프라 실패: 경고 후 통과]
  - `exit 0·no_target` → `gate_pass` + exit 0 [분기5]
  - `exit 0·no_pending` → `gate_pass` + exit 0 [분기2: 0건]
  - `exit 0·snapshotted` → `gate_warn`(박제 목록) + `gate_pass` + exit 0 [분기3-a: 자동박제 완전 성공]
  - `exit 20·disabled` → `gate_warn`(안내 1회) + `gate_pass` + exit 0 [분기1: F16 미설정]
  - `exit 50·verify_failed` → `gate_warn`(raw 보존됨 + 실패 게이트명) + `gate_pass` + exit 0 [분기3-b: 카탈로그만 실패, 경고 후 통과]
  - `exit 55·catalog_unparsed` → `gate_warn`(raw 보존됨 + 미인지 형상) + `gate_pass` + exit 0 [분기3-b]
  - `exit 30/40/45/60/70` → `gate_block`(사유+수동 절차+끄는 방법) + exit 2 [분기4: 실패 차단 — `scan_error`·`precondition_failed`(F9)·`unmapped_blocking`(F12)·`write_failed`·`busy`]
  - 그 외 종료 코드(1,10,127,…) → `gate_warn` + `gate_pass` + exit 0 [인프라 실패: exit 10(`pending`)이 나오면 계약 위반이므로 이 분기로 떨어뜨린다]
- [ ] **차단 종료 코드는 기존 게이트와 동일하게 `exit 2`이고 `gate_block`을 호출**한다.
- [ ] **"조용한 통과" 금지**: 모든 통과 경로가 `gate_pass`를 호출한다(미박제 0건 / 자동박제 성공 / kompound 미설정 전부 포함).
- [ ] **T1 실패 승계 노출(A-2)**: `gate` 호출 결과의 `inherited_warning`(T-11이 조립) 값이 있으면 그 verdict 처리와 **무관하게** 먼저 `gate_warn`으로 출력한다. `FAILED`/`GIVEN_UP`=실패 톤, `CATALOG_PENDING`=정보 톤("raw는 보존·커밋됐고 카탈로그가 뒤처져 있다") — 두 톤이 서로 다른 문구임을 테스트로 단정.
- [ ] fixture로 kompound dirty 상태를 주입했을 때, 게이트가 (i) raw 복사를 시도하지 않고(부작용 없음) 바로 `exit 2`(`precondition_failed`)로 진입함을 검증(F9 선행 확인).
- [ ] kompound 경로 미설정 환경에서 게이트가 `gate_pass`로 종료됨을 검증(F16 연동).
- [ ] **raw만 성공·카탈로그 뒤처짐** fixture((i) 성공+즉시 커밋, (ii)는 F8 실패 또는 `catalog_unparsed`)에서 raw 커밋 유지 + 카탈로그만 롤백 + **차단되지 않고 경고 후 통과**함을 검증(A-5 커밋 경계).
- [ ] **spec F2 Acceptance의 5개 분기 전부**를 커버하는 테스트가 존재: kompound 미설정 통과 / 0건 통과 / 자동박제 성공 통과(하위: (i)(ii) 모두 성공 · raw만 성공·카탈로그 뒤처짐 — 둘 다 경고 후 통과) / (i) raw 복사 실패 차단(F9·`write_failed`·F12) / 무관한 Bash 명령 무개입. **F8 검증 게이트 실패는 이 분기 집합에서 차단 사유가 아니다**(성공 통과 분기의 하위 경로로만 등장).

### F14 — hooks.json 등록
- [ ] `hooks/hooks.json`이 유효한 JSON이다.
- [ ] `PreToolUse` → `matcher: "Bash"` 배열의 **마지막**(`e2e-gate.sh` 다음)에 `${CLAUDE_PLUGIN_ROOT}/hooks/enforcement/kompound-snapshot-gate.sh` 항목이 정확히 1개 추가된다.
- [ ] 기존 5개 항목(`dangerous-command.sh`, `secret-detect.sh`, `branch-gate.sh`, `worktree-add-gate.sh`, `e2e-gate.sh`)이 **이 순서 그대로** 보존된다(T-1이 만든 `tests/test_hooks_json_contract.py`가 이 등록 후에도 GREEN이어야 함 — 재실행으로 확인).
- [ ] `worktree-add-gate.sh`와 상호 간섭이 없다(전자는 `git add`/`checkout`/`switch`만, 신규 게이트는 `git worktree remove`/`rm -r`만 처리).

## 의존 태스크
T-1(F17 회귀 안전망 GREEN — 필수 선행), T-11(cli.py의 `gate` 서브커맨드)

## 예상 변경 파일
- `hooks/enforcement/kompound-snapshot-gate.sh` — 신규(protected)
- `hooks/hooks.json` — 수정(protected)
- `tests/test_kompound_snapshot_gate_script.py` — 신규(bash 서브프로세스 통합 테스트)

## Steps
- [ ] `kompound-snapshot-gate.sh` 작성 — `worktree-add-gate.sh` 골격 복제(`lib/constants.sh`·`lib/logging.sh` 소싱, INPUT 파싱, tool_name/command 확인)
- [ ] bash 프리필터 case 문 작성(`*worktree*remove*|*rm\ -r*|*rm\ -f*|*--recursive*`)
- [ ] 코어 `gate --command "$COMMAND" --json` 호출 + JSON 파싱(`jq`, 기존 게이트 전제 A5) + exit code 분기 로직(11개 케이스 표 그대로) 구현
- [ ] `inherited_warning` 승계 노출 처리(톤 분리)
- [ ] `hooks/hooks.json`의 `PreToolUse`>`Bash` 배열 마지막에 신규 게이트 항목 추가
- [ ] `tests/test_kompound_snapshot_gate_script.py` 작성 — 11개 분기 각각 stdin JSON + mock/fixture로 코어 종료코드를 시뮬레이션(코어를 실제로 fake_kompound에 대해 돌리는 통합 케이스 최소 2~3개 + 나머지는 코어 응답을 stub) + spec F2 Acceptance 5분기 전부
- [ ] T-1의 `tests/test_hooks_json_contract.py` 재실행 — 기존 5개 보존 + 신규 1개 추가로 GREEN 확인
- [ ] `pytest tests/ -q` 전체 회귀 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_gate_script.py -q
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_hooks_json_contract.py -q   # T-1 회귀 재확인(등록 후)
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q
```

## 테스트 스코프
`tests/test_kompound_snapshot_gate_script.py` + `tests/test_hooks_json_contract.py` — 또는 `pytest tests/ -k "kompound_snapshot_gate or hooks_json"`
