# T-7: F1 런타임 상태 — 무장·상태 6종·안내 1회·블록 예산 (`runtime_state.py`)

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F1(§전문, 특히 무장/멱등/블록예산 관련 Acceptance), F16(§안내 1회)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §5.1.2(확정 사항 표 — 상태 필드 위치·상태 값 6종·블록 상한), §5.1.3("박제 미완이면 전진 금지"의 판정 — 4조건 AND, 판정 결과별 동작 표, T1의 (i)/(ii) 정책), §5.1.4(서킷브레이커와의 조화, A-1 원칙), §6.1 "④ 미설정 안내 1회의 기억 위치"(M-18, `runtime_state`가 유일한 판정 지점)

## 구현자
sdd-python-engineer

## 테스트 타입
단위 (상태 전이 — arch §9.1 "T1 상태 전이 (D-1)" 행 및 "T1 훅 통합" 행의 일부)

## 완료 조건
- [ ] 상태 파일 위치가 정확히 `<project_root>/.claude/state/kompound-snapshot.json`이다(`pipeline.json`이 아님 — C3 근거).
- [ ] 상태 값이 정확히 6종: `PENDING` | `CATALOG_PENDING` | `DONE` | `SKIPPED_UNCONFIGURED` | `FAILED` | `GIVEN_UP`.
- [ ] **무장(arming) 판정**: `ORCHESTRATOR_STATE.md`의 (feature, 상태, result 문서 경로) 서명을 baseline으로 기록하고, **서명이 baseline과 달라졌을 때만** 무장한다. 첫 관측은 baseline 등록이며 발화하지 않는다.
- [ ] **STATE 신선도**: `ORCHESTRATOR_STATE.md`의 mtime이 `state_max_age_hours`(기본 24, config 주입) 이내인지 판정하는 보조 조건 함수(주 방어 아님, T-n 근거 그대로 구현 — 미통과 시 baseline은 그래도 갱신한다).
- [ ] STATE 파서가 `- 상태: <VALUE>`와 `status: <VALUE>` **둘 다** 허용한다(§10.3 발견 사항 계승 — 기존 결함을 계승하지 않는다).
- [ ] **블록 예산**: `KOMPOUND_MAX_BLOCKS = 3`(자체 카운터 전용, 기존 `CB_MAX_BLOCKS=20`과 상태 공유 없음). `armed_session_id`가 현재 세션과 다르면 `blocks`를 0으로 초기화(세션 격리).
- [ ] **`pending`은 프리픽스가 매핑된 미박제 문서만 센다** — F12 `unmapped` 문서는 별도 집계이며 `pending`에 합산되지 않는다(이 태스크는 이 분리 계약을 받아 쓰는 쪽 — 실제 카운팅은 T-11 cli가 조립하지만, `runtime_state`의 판정 함수 시그니처는 `pending_count`와 `unmapped_count`를 별개 인자로 받는다).
- [ ] **block 반환 조건은 런타임 상태 write 성공 시에만**(A-1 원칙) — 판정 함수는 "이 판정이 block으로 이어지려면 상태 write가 먼저 성공해야 한다"는 순서를 강제하는 API로 설계한다(예: `record_and_decide()`가 write 실패 시 무조건 `{"action": "pass", "reason": "state_write_failed"}`류를 반환).
- [ ] 판정 결과 표(arch §5.1.3)를 정확히 구현: 무장 안 됨/STATE 오래됨/상태≠COMPLETED → 아무 것도 안 함(baseline만 갱신) / config 미해석 → 통과 + `SKIPPED_UNCONFIGURED` + 안내 1회 / `pending==0` → 통과 + `DONE` / **직전 상태가 `CATALOG_PENDING`** → 통과(**`DONE`과 동일 취급**, `blocks` 미증가) / `pending≥1, blocks<3` → block + `PENDING`, `blocks+=1` / `pending≥1, blocks==3` → 마지막 1회 block("3회 안내했으나 미완 — T2가 재차 막는다" 문구 포함) 후 `GIVEN_UP` / 런타임 상태 write 실패 → block 안 함(통과+경고) / 코어 예외·import 실패 → 통과 + `FAILED`(블록 예산 미소모).
- [ ] **`CATALOG_PENDING` 확정 규칙(D-1)**: `pending≥1` 판정보다 **앞서** `CATALOG_PENDING` 여부를 검사한다(그렇지 않으면 `pending`이 여전히 ≥1로 읽혀 block으로 흐른다). 재차 block하지 않고 `blocks`도 증가하지 않음을 단정하는 테스트가 있다(전후 `blocks` 값 비교).
- [ ] 상태 전이: `CATALOG_PENDING` → (카탈로그 성공) `DONE` / (새 사이클 무장, 서명 변화) `PENDING`.
- [ ] **안내 1회 판정 — `should_emit_unconfigured_notice()`가 유일한 소유자**: 프로세스 내 플래그(한 프로세스에서 몇 번 물어도 최초 1회만 `True`) + 호출 간 상태(`notice = {"session_id","at"}`, 동일 `CLAUDE_SESSION_ID`에 1회, session id 없으면 `at` 기준 24시간 창). 동일 실행 내 정확히 1회만 출력됨을 검증하는 테스트가 있다.
- [ ] `runtime_status`의 값 집합이 §5.1.2의 상태 값 목록과 **정확히 동일**하다(단일 진실은 이 모듈).

## 의존 태스크
T-2 (패키지 스켈레톤). `hooks.lib.self_improve.state_io`(기존, 무변경)의 `atomic_write`/`load_state`/`now_iso`/`parse_iso`를 **단방향 재사용**한다(역방향 의존 금지, arch §4).

## 예상 변경 파일
- `hooks/lib/kompound_snapshot/runtime_state.py` — 신규
- `tests/test_kompound_snapshot_runtime_state.py` — 신규

## Steps
- [ ] 상태 파일 스키마 정의 + `hooks.lib.self_improve.state_io` 재사용 배선(atomic write)
- [ ] STATE 파서(`- 상태:`/`status:` 양쪽 허용) + mtime 신선도 함수
- [ ] 무장 판정(서명 baseline 비교) 함수
- [ ] 블록 예산 카운터(세션 격리, `KOMPOUND_MAX_BLOCKS=3`) + write-성공-후-block 원칙 강제 API
- [ ] 판정 표 전체를 구현하는 메인 판정 함수(`decide_arming`류) — `CATALOG_PENDING` 우선 검사 순서 포함
- [ ] 안내 1회 판정(`should_emit_unconfigured_notice`) — 프로세스 내 + 세션/24h 창
- [ ] `tests/test_kompound_snapshot_runtime_state.py` 작성 — 판정 표의 모든 행(무장 안 됨/오래됨/미설정/0건/`CATALOG_PENDING`/`pending≥1` 3단계/write 실패/코어 예외) 각각 케이스, `CATALOG_PENDING`에서 `blocks` 미증가 단정(D-1), 세션 전환 시 blocks 리셋, 안내 1회(동일 세션 재호출 시 억제, 세션 전환 또는 24h 경과 시 재출력) 케이스
- [ ] `pytest tests/test_kompound_snapshot_runtime_state.py -v` GREEN 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_runtime_state.py -q
```

## 테스트 스코프
`tests/test_kompound_snapshot_runtime_state.py` — 또는 `pytest tests/ -k "kompound and runtime_state"`
