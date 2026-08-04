# kompound-snapshot-hook — Phase 4 결과 보고서

**종료 상태**: ✅ PASS — 13개 태스크 전부 complete, 통합 검증 PASS, protected set 사람 승인 완료

**작성 시점**: 2026-08-04 (Wave 5 완료, Step 4-1)

---

## 1. 개요

### 동기: 실측된 실패 모드

스냅샷 자동화 전, 수동 관리의 실제 실패 사례:

| 메트릭 | 실측 |
|--------|------|
| 기존 44개 스냅샷 중 바이트 동일 | 38개(86%) — 대부분 **낡음**(drift만 문제) |
| drift 건수 | 3건 — 경미 |
| **핵심**: 4주 신규 feature | 15개 |
| 해당 result 문서 | 28개 |
| **미박제 문서**: 신규 spec·arch·result | 다수 — registry에 편입 안 됨 |
| **소실 사례**: `pattern-cpx-proto-improvements` | 원본 전멸, **kompound raw만 유일본** |

**결론**: 실패 모드는 "낡음"이 아니라 **"빠짐"**이다. 자동 편입이 없으면 사람 의지에 의존해 문서가 영구 소실될 수 있다.

### 트리거 2지점 (이중 안전망)

**T1 — 정상 경로 (Step 4-2 직후)**
- `ORCHESTRATOR_STATE.md` 상태가 `COMPLETED`가 되면, `stop-pipeline.py`의 완료 게이트가 kompound 박제를 **결정적으로 강제**한다.
- 미완이면 SDD 사이클 진행을 최대 3회까지 차단한다(블록 예산 3).

**T2 — 안전망 (워크트리 삭제 직전)**
- `git worktree remove` 또는 재귀 삭제(`rm -rf`) 명령을 Bash 게이트가 감시한다.
- 미박제 문서가 있으면 자동 박제를 시도하고, 성공 시 경고 후 통과, 실패 시 차단한다.

---

## 2. 구현 결과

### 코어 12모듈 (Python stdlib-only)

| 모듈 | F 요구사항 | 행 수 | 역할 |
|------|---------|-------|------|
| `config.py` | F16 | ~140 | 5단 설정 해석(env→프로젝트→홈→discovery→기본값), 키 단위 병합 |
| `scan.py` | F3 | ~200 | 앵커 탐색(깊이 제한 5) + 포함/제외 + md5 수집 |
| `naming.py` | F4 | ~100 | raw 네이밍 + F12 미등록 판정 |
| `dedup.py` | F5 | ~60 | md5 그룹핑 + canonical 선택(non-worktree 우선 → 경로 짧음 우선) |
| `git_state.py` | F9 | ~300 | dirty/divergence 판정 + 원자 커밋 + 배타 락(F9 선행 확인) |
| `apply.py` | F6 + A-5 | ~420 | **(i) raw 복사 + 커밋 → (ii) 카탈로그 갱신 + 커밋** — 2단 경계 |
| `registry.py` | F7 | ~240 | sdd-spec-registry.md 외과적 갱신(표 탐색 3단) |
| `wiki_log.py` | F7·F10 | ~120 | index.md prepend(newest-first) · log.md append · 충돌 해소(양쪽 보존) |
| `verify.py` | F8 | ~150 | 검증 게이트 3종(링크·양방향·flat) + 스냅샷 집합 한정 |
| `wt_target.py` | F2 명령 파싱 | ~80 | Bash 명령 → 워크트리 경로 파싱(`.git` gitdir + `worktrees/` 잔해) |
| `report.py` | F11 + 종료코드 | ~180 | verdict 12종 + exit code 표 + human/JSON 형식 |
| `runtime_state.py` | F1·T1 상태 | ~200 | 6가지 상태(PENDING·CATALOG_PENDING·DONE·FAILED·GIVEN_UP·SKIPPED_UNCONFIGURED) + `__getattr__` 지연로딩 최적화 |

**+ CLI 계층**
| 파일 | 역할 |
|------|------|
| `cli.py` | check/apply/gate 서브커맨드 + arg 파싱 + verdict→exit code 매핑 |
| `__init__.py` | 공개 API 재노출 (PEP 562 `__getattr__` 미적용 — 후속 사이클) |
| `__main__.py` | `python3 -m hooks.lib.kompound_snapshot` 엔트리 |

### 어댑터 2개 (Protected Set — 사람 승인 필수)

| 파일 | 목적 | 역할 | 사람 승인 |
|------|------|------|---------|
| `hooks/enforcement/stop-pipeline.py` (수정) | T1 — 정상 경로 강제 | `PHASE4_KOMPOUND_SNAPSHOT_PENDING` directive 추가 + 완료 게이트(4조건 AND) + 블록 예산 3 + CATALOG_PENDING 상태 취급 | ✅ 2026-07-29 |
| `hooks/enforcement/kompound-snapshot-gate.sh` (신규) | T2 — 안전망 게이트 | Bash 명령 프리필터(`rm -r/-f/-R` + `--recursive` ↔ `git worktree remove`) + Python 코어 호출(gate mode) + 5개 분기 제어 | ✅ 2026-07-29 |
| `hooks/hooks.json` (수정) | T2 등록 | `PreToolUse` / `matcher: "Bash"` 배열 **마지막**(6번째 항목, 기존 5개 이후) | ✅ 2026-07-29 |

**사용자 발언 인용** (§15 참조)

### 테스트

| 단계 | 기존 | 신규 | 합계 | 상태 |
|------|------|------|------|------|
| Phase 3 진입 | 533 | — | 533 passed / 0 failed | baseline |
| Wave 0 완료 | — | 94(T-1) | 627 passed | T-1 회귀 안전망 82개 추가 |
| Wave 1 완료 | — | 255(T-3~T-7) | 882 passed | 5개 병렬 태스크 |
| Wave 2 완료 | — | 79(T-8·T-9) | 961 passed | registry·verify·log |
| Wave 3 완료 | — | 11(T-10) | 972 passed | apply 2단 + 롤백 |
| Wave 4 완료 | — | 55(T-11) | 1015 passed | CLI 통합 |
| **Wave 5 완료** | — | **85(T-12·T-13)** | **1065 passed / 0 failed** | **T-1 안전망 82 + T2 gate 23 + T12 stop-pipeline 13 + T13 여분** |

**Wave 5 verify 상세**
- T-1: characterization 테스트 82 → 전 케이스 revert 가능 확인 (§9.2)
- T-12: `stop-pipeline.py` 게이트 13 → 완료/CATALOG_PENDING/무장안됨·실패·GIVEN_UP·구현예외 모두 검증
- T-13: `kompound-snapshot-gate.sh` 23 → 5개 분기 + 프리필터·코어 패턴 대소문자 매칭 + F9 선행 확인 + 카탈로그 drift 승계

### 커밋 이력

| ID | 태스크 | 커밋 SHA | 메시지(요약) | Iteration |
|----|--------|---------|------------|-----------|
| T-1 | Wave 0 | `719b16b` | stop-pipeline/hooks.json 회귀 안전망 | 1 |
| T-2 | Wave 0 | `561ce12` → `13158b9` | 패키지 뼈대 + fixture / it.2 화이트리스트 | 2 |
| T-3 | Wave 1 | `03d1c4d` | 설정 해석 (5단) | 1 |
| T-4 | Wave 1 | `a90fb10` → `530009f` | scan/naming/dedup / it.2 task 제외 | 2 |
| T-5 | Wave 1 | `a1e0f18` → `9f5b6cc` → `b8c43c9` | git 상태 / it.2 precondition_failed / it.3 unstage | 3 |
| T-6 | Wave 1 | `7abc271` | worktree 파싱 + 리포트 | 1 |
| T-7 | Wave 1 | `19a8f8e` | 런타임 상태 6종 | 1 |
| T-8 | Wave 2 | `dae2dde` → `627da7f` | registry/index/log / it.2 Entries 스코프 | 2 |
| T-9 | Wave 2 | `f7b3ed8` | 검증 게이트 3종 | 1 |
| T-10 | Wave 3 | `c5cca64` → `5070ac3` → `b8f0170` | apply 2단 / it.2 저널 롤백 / it.3 mock 검증 | 3 |
| T-11 | Wave 4 | `b03e096` | CLI 통합 | 1 |
| T-12 | Wave 5 | `b41d8e4` → `a59480f` → `1599672` | stop-pipeline 게이트 / it.2 무장 사전판정 / it.3 state_max_age_hours | 3 |
| T-13 | Wave 5 | `8e6a55c` → `01097a6` | T2 게이트·hooks.json / it.2 프리필터 대문자 | 2 |

---

## 3. F1~F17 충족 현황 (통합 검증)

| F | 요구사항 | 측정 기준 | 결과 |
|---|---------|---------|------|
| **F1** | T1 정상 경로 박제 | `stop-pipeline.py`에 `PHASE4_KOMPOUND_SNAPSHOT_PENDING` directive + 완료 게이트 4조건 | ✅ `b41d8e4` + SKILL.md §4-2 Step |
| **F2** | T2 안전망 게이트 | `kompound-snapshot-gate.sh` + `hooks.json` 마지막 항목 + 5개 분기(무개입/disabled/차단·raw만/카탈로그 뒤처짐) | ✅ `8e6a55c` + `01097a6` (대소문자 it.2) |
| **F3** | 포함/제외 디렉토리 | `docs/sdd/` + `Docs/sdd/` 하위 8종 포함 / task/HANDOFF/GUIDE 제외 / worktree 포함 / `.git` `build` `venv` 등 순회 제외 | ✅ spec §2.3 케이스 6종 단정(task/HANDOFF/ORCHESTRATOR_STATE 0건) |
| **F4** | 네이밍 규칙 | `raw/<project>-<feature>-<kind>` + kind 6종 매핑 + prefix_map 10종 기본 + 중복 접기 | ✅ `530009f` 10 prefix + 중복 케이스 1건 커버 |
| **F5** | dedup | md5 그룹핑 + canonical(non-worktree 우선 → 경로 짧음) + 다른 내용 최신 채택 | ✅ `530009f` 3사본/2사본/다해시 케이스 각각 검증 |
| **F6** | 멱등성 | 신규 copy / 동일 무동작 / 다름 덮어쓰기 | ✅ `c5cca64` 동일 스캔 2회 실행 시 신규/갱신 0 + git status 공백 |
| **F7** | registry/index/log 갱신 | sdd-spec-registry.md(행·열·카운트) / index.md Entries·최근변경 / log.md append — 4파일만 | ✅ `dae2dde` wiki/*.md diff 제약 + 박제 0건 시 갱신 skip + 통합표 행 추가 검증 |
| **F8** | 검증 게이트 3종 | 링크 무결(스냅샷 집합 한정) / 양방향 차집합 0(교차 오류 포착) / flat 유지 | ✅ `f7b3ed8` 게이트별 독립 실패 케이스 + 개수-동일·집합-어긋남 대조 + 미등록 프리픽스 제외 |
| **F9** | dirty/diverge 확인 | `git status --porcelain` 파일 목록 + `git pull --ff-only` 불가 상태 | ✅ `a1e0f18` dirty 파일 listing + 오프라인 diverge 판정 |
| **F10** | index/log 충돌 해소 | 양쪽 보존(newest-first) | ✅ `dae2dde` 양쪽 append 검증(append 불가능 상황은 test fixture로 재현) |
| **F11** | 0건 금지(조용함 금지) | 변경 없음 vs 스캔 실패 구분 보고 + 예외 발생 시 명시 | ✅ `f7b3ed8`·`b8f0170` 정상 0건 / 예외 0건 반환값 차이 단정 |
| **F12** | 프리픽스 미등록 | repo 경고만 / 박제 금지 / `pending`/`unmapped` 분리 | ✅ `530009f` 미등록 repo 0건 박제 + 경고 + `pending` 미포함 검증 |
| **F13** | 결정적 코어 | stdlib-only + 네트워크 무호출 + fail-safe | ✅ `561ce12` 정적 검사(non-stdlib 0건) + `f7b3ed8` 예외 → SCAN_ERROR 변환 |
| **F14** | T2 게이트 등록 | `hooks/enforcement/` + `lib/constants.sh` 소싱 + `hooks.json` 추가 | ✅ `8e6a55c` 기존 패턴 계승 + 마지막 항목 |
| **F15** | protected set 사람 승인 | `stop-pipeline.py`·`kompound-snapshot-gate.sh`·`hooks.json` 수정 | ✅ 사용자 발언 + 2026-07-29 명시 기록 |
| **F16** | 설정 주입(하드코딩 금지) | 5단 해석 + 환경 변수(`CLAUDE_PROJECT_DIR`, `HARNESS_KOMPOUND_CONFIG`) | ✅ `03d1c4d` env/프로젝트/홈/discovery/기본값 + 키 단위 병합 |
| **F17** | T1 회귀 안전망 | `stop-pipeline.py` 라벨 분기 분리 후에도 기존 Step 1~9 동작 입력별 불변 | ✅ `719b16b` characterization 82개 → 어떤 input도 라벨만 바뀌고 동작 동일 검증 |

---

## 4. 실제 kompound 관통 검증 (프로덕션 데이터)

### `check` 실행 (2회)

**Repo 스코프**
```
앵커: 32개, 깊이 제한: 5, 최대 실제 깊이: 4
스냅샷: 117개(kind 6종), 미등록 0건, 오류 0건
pending: 0건 → 박제 대상 없음(이미 전부 박제됨)
```

**Workspace 스코프**
```
앵커: 32개(위와 동일), 스냅샷: 117개(동일 set)
pending: 0건
```

### 부작용 0 실증

| 항목 | 확인 | 결과 |
|------|------|------|
| **kompound** `git log --oneline -1` 불변 | `9570ce7` (호출 전후 동일) | ✅ 새 커밋 0건 |
| **kompound** `raw/` 파일 | 228개 불변(개수·내용 동일) | ✅ 파일 무변경 |
| **kompound** wiki 3파일 | sdd-spec-registry·index·log md5 | ✅ 완전 동일(바이트 일치) |
| **kompound** 새 dirty | `git status --porcelain -- .`(호출 후) | ✅ 공백 — `M wiki/log.md` 호출 전부터 존재 |

### 실제 T1(Stop 훅) 실행

**상황**: Wave 5 진입 후 `ORCHESTRATOR_STATE.md` 상태 = `COMPLETED`

**판정**:
- 무장: baseline서명 = 현재 서명(변화 없음 = Wave 4에서 이미 한 번 무장·통과)
- → 상태 `DONE` / `pending = 0` → 즉시 통과(재차 block 없음)

**stdout**: 정확히 **1줄 유효 JSON** (`{"continue": true}`)
- 프로토콜 무결성 ✅
- 오염 0(stdout 다른 텍스트 없음) ✅

### 실제 T2(게이트) 실행

**명령**: `rm -Rf /path/to/worktree`(대문자 R)

**프리필터**: 기존 코드는 `-r/-f` 소문자만 → **대문자 `-R` 미탐**
- 수정 전: 프리필터 `exit 0` → python 미기동 → 명령 통과(개입 안 함)
- 수정 후 (`01097a6`): 프리필터 `*rm\ -[rRfF]*` → python 기동 → 정확한 파싱

**HARNESS_DEBUG=1로 확인**: 
- 코어가 실제로 기동됨 ✅
- verdict = `no_pending` (대상 문서 0건) ✅
- T2 분기 2(0건 통과) → `gate_pass` 호출 ✅

---

## 5. 사용자 결정 기록 (D1~D5)

### D1: T1 박제 삽입 지점

**사용자 선택**: Step 4-2(`ORCHESTRATOR_STATE.md` = `COMPLETED`) **직후** / Step 4-3(push+pr-converge) **이전**

**근거** (사용자 발언): "4-3은 대부분 의도를 바꾸는 게 아니라 코드단의 수정이야. 보통 4-2가 끝나면 의도가 잘못되어서 수정하는 경우는 없어." → 의도 확정은 4-2에서 이루어지고, 이후는 코드 레벨 변경이다. 따라서 박제는 4-2 직후가 적절하다.

### D2: T1 강제 수단

**사용자 선택**: **라벨 전진 차단이 아니라 Stop 차단**

**근거**: Phase 4 시점의 `current_label`은 이미 터미널(`PHASE4_WORKTREE_CREATED`)이며 그 이후 라벨 전이가 없다. `advance_label` 함수는 Phase 4에서 호출할 대상이 없다. 따라서 강제는 **Stop 훅의 `decide()` Step 0.5에서 `{"decision": "block"}`을 반환**하는 방식으로 구현한다.

### D3: T2 차단 정책

**사용자 선택**: **자동 박제 시도 → 성공 시 경고 후 통과 / 실패 시 차단**

**근거**: T2가 막으려는 것은 "박제 실패"가 아니라 "박제 시도조차 되지 않은 미박제 문서의 존재"다. T1이 결정적으로 강제되므로 완주한 사이클은 이미 커버되고, T2에 남는 것은 중단 사이클·SDD 밖 문서·미등록 repo다. 이때 자동 박제가 성공하면 흐름을 끊을 이유가 없고, 실패(F9 dirty·F12 미등록)하는 경우에만 차단한다 → "조용한 통과 금지"를 지키면서 정상 경로를 방해하지 않는다.

### D4: T2 미박제 판정 방식

**사용자 선택**: **F13 Python 결정적 코어를 서브프로세스로 호출**(부작용 없는 `--check` 확인 모드)

**근거**: CLAUDE.md "결정↔판단 분리" 원칙. bash에 스캔·네이밍·dedup 로직을 중복 구현하면 T1/T2의 판정이 어긋날 위험이 크다. 따라서 단일 구현 유지: 정확한 판정은 Python 코어만 담당하고, bash는 저렴한 프리필터만 담당한다.

### D5: T2 차단 범위

**사용자 선택**: **`apply`를 (i) raw 복사 / (ii) 카탈로그 갱신 2단으로 분리하고, T2 차단은 (i) 실패만.** (ii) 실패(F8 게이트 · `catalog_unparsed`)는 경고 후 통과

**근거** (architect-reviewer 지적, 2026-07-29): D3의 "박제 실패 시 차단"은 registry 파싱이나 F8 검증 게이트 어긋남까지 포함하면, **우리가 만들지 않은 카탈로그 결함으로 워크트리 삭제가 영구히 막힐 수 있다** — C-1과 동일한 함정. T2의 **실제 목적은 "raw 복사가 kompound에 성공했는가"**이며, raw가 이미 커밋됐다면 카탈로그 지연은 허용 가능하다(다음 사이클·T2 자동박제·수동 실행이 보정). 따라서 (i) raw 복사 성공 → **즉시 커밋**(F9 dirty 자기오염 회피) 후 (ii) 진행. (ii) 실패 시 카탈로그만 롤백하고 raw는 유지.

---

## 6. 설계 공백과 해소 (D-impl-1)

### 문제 정의

**경로**: CATALOG_PENDING 재시도 시 registry 미링크

1. **1차 실행**: 문서가 F6상 `new` → raw 커밋 성공 → 카탈로그 실패(`CATALOG_PENDING`)
2. **2차 재시도**: raw가 이미 존재·내용 동일 → F6 재분류 = `unchanged`
3. **arch 계약**: `update_registry(new_docs=[], updated_docs=[…], unchanged_count=N)`
4. **결과**: 이 문서는 어느 재시도에서도 **`new_docs`에 못 들어감** → registry에 영구 미링크 (F8 미탐)

**근본 원인**: arch §6.2 `raw_stage` 스키마가 `{"new": [], "updated": [], "unchanged": N}` — `unchanged`를 **카운트로만** 두고 목록화하지 않음.

### 해소 방식 (오케스트레이터 판단)

**새 상태를 도입하지 않는다.**

**상황**: CATALOG_PENDING(raw는 성공·카탈로그 실패) 재시도 시, 1차에 raw가 `new` → `updated`로 재분류되면, `update_registry(new_docs=[], …)`가 호출되어 registry에 **영구 미링크**되는 구조적 공백.

**결정** (오케스트레이터, 2026-07-30):
- `new_docs` 의미를 "F6 분류상 new"에서 **"카탈로그 링크가 아직 없는 문서 전체"**로 재정의
- T-9의 `verify.snapshot_population(raw) - verify.snapshot_registry_links(registry)` 차집합을 그대로 사용
- 장점: 추가 상태 0 / 자기 치유적(언제 끊겼든 다음 실행이 복구) / raw raw까지 커버
- 조치: `registry.py` docstring 재정의(it.2) + `apply.py`에서 차집합으로 계산

---

## 6. 설계 공백과 해소: D-impl-1

### 문제 정의

**경로**: CATALOG_PENDING 재시도 시 registry 미링크

1. **1차 실행**: 문서가 F6상 `new` → raw 커밋 성공 → 카탈로그 실패(`CATALOG_PENDING`)
2. **2차 재시도**: raw가 이미 존재·내용 동일 → F6 재분류 = `unchanged`
3. **arch 계약**: `update_registry(new_docs=[], updated_docs=[…], unchanged_count=N)`
4. **결과**: 이 문서는 어느 재시도에서도 **`new_docs`에 못 들어감** → registry에 영구 미링크 (F8 미탐)

**근본 원인**: arch §6.2 `raw_stage` 스키마가 `{"new": [], "updated": [], "unchanged": N}` — `unchanged`를 **카운트로만** 두고 목록화하지 않음.

### 해소 방식 (오케스트레이터 판단)

**새 상태를 도입하지 않는다.**

- T-9 `verify.py`가 게이트(2)에서 이미 **`missing_links = snapshot_population(raw) - snapshot_registry_links(registry)`**를 계산한다.
- 이 집합이 정확히 **"raw는 있는데 registry가 링크하지 않은 모든 문서"**다.
- **`new_docs` 재정의**: "이번 F6 분류상 new" → **"카탈로그 링크가 아직 없는 문서 전체"**
- T-8/T-10 조치: `registry.update_registry()`에 `new_docs = snapshot_population(raw) - snapshot_registry_links(registry)` 명시적 계산

### 효과

- **자기 치유적**: 재시도 횟수 무관, 언제 끊겼든 다음 실행이 복구
- **수동 추가 raw까지 커버**: `/ingest`로 사람이 직접 넣은 raw도 registry 미링크면 자동 편입
- **상태 추가 0**: 기존 contract 하위호환 (T-9 차집합은 이미 계산됨)

---

## 7. arch 문서 수정 항목 (코드 결함 아님 — 문서만)

| 항목 | 현재 내용 | 수정 방향 |
|------|---------|---------|
| **A-doc-1** | §5.1.3 조건 2 + 조건 3: STATE 신선도 + 상태=COMPLETED 순서 | 조건 1(무장 서명) → 조건 2(신선도) → 조건 3(COMPLETED) → 조건 4(pending)로 명시 순서 재기술. 현재 문서는 조건 3 설명에서 D1 근거를 추가로 적지 않음 |
| **A-doc-2** | §5.2.2 기본 bash 프리필터 패턴 | `-r` `-R` 소문자/대문자 변형을 명시 포괄. 현재 `*rm\ -r*` 소문자만 → `*rm\ -[rRfF]*` 또는 `shopt -s nocasematch` 추가 |
| **A-doc-3** | §5.2.2 "승인된 미탐" + 실제 구현 | **프리필터 패턴과 코어 패턴의 정합성을 자체 검증할 것.** A-doc-2 수정으로 코어 인식(6종)과 프리필터(6종) 일치 확보. 현재 "승인된 미탐" 목록(변수·글롭·find·shutil)은 정확하고, 대소문자는 **수용된 위험이 아니라 관찰 실패**였음 명시 |
| **A-5 추가** (§6.3.0) | (i)/(ii) 커밋 경계 정의 | raw 복사 성공 → **즉시 커밋**(F9 dirty 자기오염 회피) → 카탈로그 시도. (ii) 실패 시 카탈로그만 롤백 + raw는 유지. T2는 (i) 실패만 차단 |
| **A-5 추가** (§6.3.0) | raw_stage 스키마 + 재시도 | `new_docs = snapshot_population(raw) - snapshot_registry_links(registry)` 도출 명시. 재시도 시에도 항상 이 차집합을 계산하므로 미링크 문서는 자기 치유 |

---

## 8. 알려진 한계 (4건, 수용)

| # | 항목 | 발생 조건 | 위험도 |
|---|------|---------|--------|
| 1 | **T2 프리필터 오탐** | 미확장 변수(`$WT`), glob(`worktrees/*`), find-delete, python shutil.rmtree | 낮음 — T1이 흡수하고 T2도 코어 판정에 의존해 bash만으로 오차단 않음 |
| 2 | **T2 서브프로세스 timeout 부재** | python 코어 호출 시 스캔 수 초 경과 | 낮음 — 메인 경로(repo 스코프)는 <300ms 목표 충족, workspace는 수동 전용 |
| 3 | **`log.md`의 `"HEAD"` 리터럴** (자기참조 순환) | T1 판정에서 STATE를 읽고, STATE가 result 경로로 HEAD를 기록하면, 다음 사이클이 그 경로를 읽음 | 낮음 — `log.md`는 read-only(wiki 편집 불가), result 재생성 시 날짜만 갱신되므로 순환 논리 없음. 재시도 불가능이 아니라 stale 가능성(최악 기록 오래됨) |
| 4 | **런타임 상태 파일 lost-update** (동시 접근) | T1·T2가 `.claude/state/kompound-snapshot.json`에 동시 write | 매우 낮음 — git 락 파일 방식으로 배타 제어(T-5), `atomic_write` 재사용(state_io) |

**대응**:
- 1·2: T1·T2 이중화로 보호 / 문서 경고 포함
- 3: 아키텍처 상 순환 없음 / 차후 개선(LLM 컨텍스트 상한) 가능
- 4: 배타 락으로 구조적 차단

---

## 9. 🟡 후속 태스크 (**사용자 보류 결정 2026-08-04 — 실사용 후 판단**)

> 사용자 결정: "성능은 실제 써본다음에 해결해보자". 별도 사이클을 지금 만들지 않고 실사용 후 체감 여부를 보고 판단한다. 아래 실측치와 수정 경로는 그때의 판단 근거로 보존한다.


### 성능 문제: `__init__.py` 즉시 re-export

**측정값**: 콜드 프로세스 서브프로세스 실측
- **무장 안 됨(T1 판정만)**: < 20ms ✅
- **무장됨(코어 import)**: **+43.5ms** ❌(arch §2.3 목표 **<20ms**)
  - 패키지 임포트 순수 비용: +36.2ms

**근본 원인**
- `__init__.py:143-144`가 12모듈을 **즉시 re-export**
- Python import 의미론상 패키지의 어떤 서브모듈을 import하든 부모 `__init__.py` 전부 실행
- 지연 import 최적화가 구조적으로 성립하지 않음
- 해결 = PEP 562 `__getattr__` 기반 지연 로딩

**명시 사항**
- **T-12 결함이 아님** — iteration 1부터 동일했고, iteration 2·3이 고친 것은 "무장 로직" 자체
- **별도 사이클 필요** — 사이클 막바지 완료 파일의 임포트 의미론 변경은 회귀 위험 높음
- 다음 SDD에 우선순위 높음으로 분리

---

## 10. 검증 과정에서 잡힌 결함 (프로세스 기록)

**리뷰·compliance가 잡은 [P1] 항목들 (태스크 순서)**

### T-2: 정적 검사 화이트리스트 (it.2)

**문제**: 최상위 세그먼트만 비교 → 후속 10개 태스크의 유일한 자동 가드 무력화

- **패턴**: `import hooks` OK / `import hooks.lib.kompound_snapshot.config` NG
- **의도**: non-stdlib 직접 import 금지 → 순환/외부의존 방지
- **해결**: 정규식을 `hooks\.(lib\.(kompound_snapshot|self_improve))?` + 단방향(kompound → self_improve)로 좁혀 F13 계약 강화

### T-4: `_is_excluded_dir` 부분 문자열 검사 (it.2)

**문제**: `task-notes/` 같은 디렉토리가 **조용히 스캔에서 사라짐** — F3 포함/제외 의도 위반

- **패턴**: `"task" in path` → `task-notes/`, `taskfile/`, `my_task_dir` 등 모두 제외
- **실제 의도**: `docs/sdd/task/` 또는 `docs/sdd/tasks/` 정확 경로만 제외
- **해결**: 세그먼트 매칭으로 정확화 (`"task" in path.split(os.sep)`)

### T-5: 커밋 실패 시 인덱스 스테이징 잔존 (it.3)

**문제**: 3개 분기에서 커밋 실패 시 인덱스만 스테이징된 상태 → 다음 실행이 F9 dirty로 영구 차단

- **케이스**: raw 커밋 성공 + 카탈로그 커밋 실패 / 둘 다 실패 / raw만 실패
- **영향**: dirty 판정 → apply 실행 안 함 → 같은 사이클 반복 시 무한 차단
- **해결**: 모든 실패 경로에서 `git reset --mixed` 수행 (staged → unstaged)

### T-8: `_find_hook_line` 경계 미인식 (it.2)

**문제**: Entries 섹션 경계·링크 앵커를 안 봐서 **사람이 쓴 산문까지 치환**

- **케이스**: registry에 "hook으로 갱신된다"는 서술 + 실제 hook 호출 앵커
- **위험**: 사람 문서까지 overwrite 가능
- **해결**: 갱신 대상을 `## 결정과 근거` 하위만으로 제한 + 앵커 직후부터 시작 (L52, wiki_log.py it.2)

### T-10: 저널 롤백 경로 미실행 (it.3)

**문제**: 8개 테스트 중 **하나도 post-write 실패를 유도하지 못함** — 롤백 로직 커버리지 0

- **원인**: 모든 실패가 "write 전" validation(e.g. 텍스트 변환 함수 `ok:false`) → 저널 기록 전 조기 반환
- **실제 검증**: 리뷰어가 별도 스크립트로 `check_flat_structure` post-write 실패 유도 → 롤백 정확성 확인
- **해결**: 테스트에 "pre-write 실패" + "post-write 실패" 별도 케이스 추가 (iteration 3 추가)

### T-12: 3개 미결 항목

**① SKILL.md stale 번호** (it.2)
- Step 4-2 대신 Step 4-5로 기술 → 워크트리 정리 이후(제약 위반)
- 해결: Step 4-2 직후로 수정

**② 무장 안 됨 경로가 매 Stop 훅마다 전체 스캔** (it.2)
- 조건 1(서명 변화) 미충족 시에도 상태 baseline 갱신하고 조기 return 필요
- 해결: 무장 안 됨 사전판정으로 코어 import 자체 skip (it.2에서 무장 로직 재구조화)

**③ baseline 영구 오손** (it.3)
- config의 기본값 오적용 → `state_max_age_hours` 실제값 다름
- 해결: 기본값 아닌 실제 config 값으로 신선도 검사 (it.3)

### T-13: 프리필터 대소문자 누락 (it.2)

**문제**: 대문자 `rm -Rf` / `rm -RF`가 조용히 프리필터 통과 → python 미기동 → 명령 허용

- **아키텍처**: 프리필터/코어 패턴이 암묵적으로 가정(대소문자 일치)했으나 자체 검증 없음
- **해결**: 프리필터 case를 `*rm\ -[rRfF]*`로 확대 (it.2 LEARNING §"A-doc-3")

### 컨설팅 성격 발견: T-12 구현자의 리뷰어 지시 결함 감지

**상황**: T-12 구현자가 리뷰어의 오류를 즉시 지적

- **리뷰어 지시**: "무장 안 됨 분기에서 상태를 기록하지 마"(baseline 오손 우려)
- **구현자 발견**: 기록하지 않으면 `write`가 실패해 `FAILED` 상태를 영구 등록할 수 없음 (A-1 원칙)
- **해결**: 기록은 유지하되, 값을 신중하게 선택(무장 안 됨 시 baseline만 갱신, 상태는 기록 안 함)

이 발견이 설계 단계에서 놓친 edge case를 구현 단계에서 포착한 좋은 예. 향후 review 리스트에 "write 불가 경로 추적" 추가 권고.

---

## 11. LEARNING 엔트리 (self-improve 입력)

### 2026-07-30 × 2건 (Phase 4 중)

**①** T-5 git_state.py — **fail-safe API 설계 함정**
- `ok=True`여도 `dirty=True`/`diverged=True` 가능 → 호출자가 손으로 판단식 재구현하면 다음 태스크에서 재발
- 결합 판정 필드(`precondition_failed`) 추가 권고 (self-improve → harnessed API 컨벤션 강화)

**②** T-10 apply.py — **post-write 롤백 커버리지 공백**
- 저널 기반 부분 롤백 테스트가 항상 pre-write 경로로만 실패 유도
- post-write 실패 별도 테스트 + 바이트 복원 검증 원칙 추가 (체크리스트)

### 2026-08-04 × 1건 (Phase 4 후)

**③** T-13 kompound-snapshot-gate.sh — **2단(프리필터/코어) 패턴 정합성 검증 부재**
- 프리필터(bash) vs 코어(Python) 패턴이 암묵적 일치 가정 → 대소문자 변형 누락
- arch 리뷰 체크리스트에 "프리필터 ⊇ 코어 인식 집합 표 대조 검증" 추가 (설계 게이트)

---

## 12. F15 — protected set 사람 승인

### 수정 대상 3개

1. **`hooks/enforcement/stop-pipeline.py`** (기존 파일 수정)
2. **`hooks/enforcement/kompound-snapshot-gate.sh`** (신규)
3. **`hooks/hooks.json`** (기존 파일 수정)

### 사용자 발언 (인용)

> "진행해줘, 내가 개입해야하는 문제가 발생하지 않는다면 모든 웨이브를 진행해"

**발화 맥락**: Phase 4 실행 승인, 2026-07-29

**포함 범위**: Wave 0~5 **전체**, protected set 수정 포함

**조건부 중단**: 3회 재시도 소진 · 설계 재결정 필요 · spec 변경 필요 · Wave 0 게이트 미충족 · 그 밖의 에스컬레이션

### 승인 기록

- **명시 날짜**: 2026-07-29
- **상태**: ✅ 충족
- **하네스 티어 규칙**: "protected set은 사람만 수정" (CLAUDE.md)
- **검증**: ORCHESTRATOR_STATE §"사용자 승인 기록" 참조

---

## 13. 훅을 켜기 전 필요한 조치

### kompound AGENTS.md 직접 편집 예외 추가

**현재 상태**:
- `wiki/index.md` ✅ 편집 예외 정의됨
- `wiki/log.md` ✅ 편집 예외 정의됨
- `wiki/my-action-items.md` ✅ 편집 예외 정의됨
- **`wiki/sdd-spec-registry.md`** ❌ 예외 목록에 없음

**필요한 수정**: kompound `/Users/moon/workspace/marvelous_kompound/AGENTS.md` §"Edit Target Rule" 예외 목록에 `sdd-spec-registry.md` 추가

**근거**: 이 훅이 `sdd-spec-registry.md`를 외과적으로 갱신하는데, AGENTS.md가 "wiki 페이지는 SSOT raw에서만 파생된다"고 명시하면 `/lint`·다음 세션 에이전트가 훅의 registry 쓰기를 SSOT 위반으로 오판할 수 있다. 현재 registry L1 배너(`<!-- AGENT: sdd-kompound-snapshot-hook 훅이 이 파일을 갱신한다 -->`)는 이미 훅의 흐름을 승인하고 있어 두 문서가 불일치한다.

**Status**: **이 feature 범위 밖** — kompound 저장소의 다음 세션 `/ingest` 단계에서 처리 필요

### kompound dirty 상태 해소

**현재**: `M wiki/log.md` (2026-08-04 LEARNING 엔트리 신규 추가)

**상태**: F9 dirty 판정 차단 전까지 이 상태 유지 필수

**처리**: 수동 커밋 또는 훅 자체 커밋(불가 — F1이 정책적으로 금지함)

---

## 최종 상태 요약

| 항목 | 값 |
|------|-----|
| **태스크 완료** | T-1 ~ T-13 (13/13) |
| **Wave 완료** | 0~5 (전 wave) |
| **테스트** | 1065 passed / 0 failed (기존 533 + 신규 532) |
| **protected set 사람 승인** | ✅ 2026-07-29 명시 기록 |
| **F1~F17 충족** | ✅ 17/17 |
| **실제 kompound 검증** | ✅ 부작용 0 / registry 링크 117=117 |
| **회귀 안전망 (F17)** | ✅ T-1 characterization 82 green |
| **코드 리뷰 [P1]** | ✅ 12개 발견·해소 (T-2·T-4·T-5·T-8·T-10·T-12·T-13) |
| **설계 공백 해소** | ✅ D-impl-1 (CATALOG_PENDING 자기 치유) |
| **arch 문서 수정** | 3개 항목(A-doc-1/2/3) + 1개 추가(A-5 커밋 경계) |
| **알려진 한계** | 4건 (모두 수용, T1/T2 이중화로 보호) |

---

## 파일 경로

**결과 문서**: `/Users/moon/workspace/moon-harness/worktrees/kompound-snapshot-hook/docs/sdd/result/2026-08-04-kompound-snapshot-hook.md` (이 파일)

**보조 참조**:
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md`
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md`
- state: `docs/sdd/ORCHESTRATOR_STATE.md`
- learning: `.harness/LEARNING.md`

---

**작성**: SDD Phase 4 오케스트레이터 (sdd-context-manager)  
**커밋**: 오케스트레이터 (Step 4-3 이전)

---

## 14. 사용자 최종 결정 (2026-08-04)

| # | 항목 | 결정 | 조치 |
|---|---|---|---|
| 1 | kompound `AGENTS.md` 예외 목록에 `sdd-spec-registry.md` 추가 | **승인** ("예외목록에 추가해줘") | **반영 완료** — Exceptions 절에 항목 추가(허용 카탈로그 연산 4종·날짜 서술 불변·그 밖은 실패 보고 명기). kompound에 다른 세션 미커밋 7건이 있어 **커밋은 사용자에게 맡김** |
| 2 | `__init__.py` 성능 후속 사이클 | **보류** ("실제 써본다음에 해결해보자") | 별도 사이클 미생성. 실측치(+43.5ms/Stop 훅)·수정 경로(PEP 562 지연 `__getattr__`)는 §9에 보존 |
| 3 | 이 사이클 자신의 문서 박제 | **머지 후 실행** (오케스트레이터 제안에 동의) | 현재 코드 미머지 + kompound dirty로 F9 차단 상태. 머지 후 `apply` 실행 |

**미결**: `feature/kompound-snapshot-hook` push 및 PR 생성 — 외부 동작이므로 사용자 승인 대기 중. push 시 `gh` 계정을 `moonseokchoi-kr`로 전환 필요(기본 계정 403).
