# Orchestrator State

## 메타
- feature: `kompound-snapshot-hook`
- spec 문서: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md`
- arch 문서: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md`
- ui 문서: 해당 없음 (SIMPLE 모드)
- api 문서: 해당 없음 (SIMPLE 모드)
- task 디렉터리: `docs/sdd/task/kompound-snapshot-hook/` (T-1 ~ T-13, 13개)
- 시작 시각: 2026-07-29T00:00:00+09:00
- 마지막 갱신: 2026-07-29 (Phase 3 dag 모드 — STATE 초기 생성)
- 상태: **PAUSED_AT_LIMIT** (2026-07-29 → 30, 조직 월 지출 한도 초과)
- 워밍업 완료: 미실행(fast-scoped)

### 사용자 승인 기록 (protected set — spec F15)
- **2026-07-29 Phase 4 실행 승인**: 사용자가 "진행해줘, 내가 개입해야하는 문제가 발생하지 않는다면 모든 웨이브를 진행해"로 **Wave 0~5 전체 실행을 승인**했다.
- 이 승인은 **Wave 5의 protected set 수정(T-12 `hooks/enforcement/stop-pipeline.py` / T-13 `hooks/enforcement/kompound-snapshot-gate.sh` 신규 + `hooks/hooks.json`)을 포함**한다. CLAUDE.md의 "게이트 스크립트는 사람만 수정" 조건은 이 명시적 지시로 충족됐다.
- 단 **사용자 개입이 필요한 사건**(3회 재시도 소진 · 설계 재결정 필요 · spec 변경 필요 · Wave 0 게이트 미충족 · 그 밖의 에스컬레이션)이 발생하면 즉시 중단하고 보고한다. 그 외에는 Wave 사이에서 멈추지 않는다.

> 단일 오케스트레이터 모드 — **팀 배정 섹션 생략**(사용자 지시). Wave 0의 T-1/T-2 병렬은 곧바로 Wave 1으로 수렴하는 단일 체인이며, 독립 클러스터가 2개 이상 존재하지 않는다.

---

## 빌드 프로파일

> arch 문서 `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` §"빌드 프로파일" 표를 그대로 복사. Phase 4 build-aware TDD가 소비.
> 출처: `CLAUDE.md` (moon-harness repo 루트, 2026-07-29 확인)

| 필드 | 값 | 비고 |
|------|-----|------|
| 유형 | fast-scoped | 빌드 산출물 없음. pytest를 직접 실행한다(순수 Python + bash) |
| 워밍업 빌드 | — | fast-scoped — Phase 4 진입 워밍업 생략 |
| 증분 빌드 | — | 컴파일 단계 없음 |
| 테스트 실행 | `PATH="/opt/homebrew/bin:$PATH" python3 -m pytest {filter} -q` | `{filter}`=태스크 스코프 자리표시자. 전량은 `{filter}`=`tests/` |
| 테스트 필터 문법 | `tests/test_kompound_snapshot_naming.py` · `tests/test_kompound_snapshot_naming.py::TestPrefixMap` · `tests/ -k "kompound and naming"` | 파일 / 클래스 / 키워드 3형태 |
| clean 정책 | no-clean | 태스크 간 clean 금지. `__pycache__`·`.pytest_cache` 유지 |

> 📌 pytest는 homebrew python(3.14)에만 설치되어 있다. `PATH` 프리픽스를 빼면 Xcode python3가 잡혀 실패한다.

> 워밍업 실행 여부 기록: `워밍업 완료: 미실행(fast-scoped)`

---

## Wave 0 게이트 (실행 규칙 — spec F17, Wave 순서만으로 표현 안 되는 추가 조건)

> **T-1(F17 회귀 안전망)이 GREEN으로 확인되기 전에는 Wave 5(T-12, T-13)를 시작하지 않는다.**
> 정상 경로에서는 T-1이 Wave 0에서 이미 실행·GREEN 확인되므로 Wave 4 완료 시점엔 자명히 충족되어 있다. 그러나 **재개(resume)·중단(interrupt) 시나리오**에서 T-1이 여전히 `pending`/`interrupted`/`escalated` 상태로 남아 있을 수 있으므로, 오케스트레이터는 **Wave 5 진입 직전에 반드시 태스크 상태 테이블에서 T-1의 Status가 `complete`인지 재확인**한다. `complete`가 아니면 Wave 5를 보류하고 사용자에게 보고한다(protected set 진입 조건이므로 임의로 스킵 불가).
> 이 조건은 T-12/T-13 각각의 "사람 승인 필요"(F15, 아래 태스크 상태 표 참조)와는 **독립적인 별도 조건**이다 — 둘 다 충족되어야 Wave 5가 시작된다.

---

## Wave 구성

| Wave | 태스크 | 구현자 | 의존성 | 동시 실행 최대 |
|------|--------|--------|--------|--------------|
| 0 | T-1, T-2 | sdd-test-automator(T-1, refactor 모드), sdd-python-engineer(T-2) | 없음 | 2 |
| 1 | T-3, T-4, T-5, T-6, T-7 | sdd-python-engineer × 5 | T-2 | 5 |
| 2 | T-8, T-9 | sdd-python-engineer × 2 | T-3, T-4 | 2 |
| 3 | T-10 | sdd-python-engineer | T-4, T-5, T-8, T-9 | 1 |
| 4 | T-11 | sdd-python-engineer | T-3~T-10 전체 | 1 |
| 5 | T-12, T-13 | sdd-python-engineer(T-12), sdd-implementer(T-13) | **T-1 GREEN(Wave0 게이트)** + T-11 + (T-12만 T-7도) | 2 |

**DAG 표현:**
```
Wave 0: T-1 (F17 안전망, refactor)        T-2 (패키지 뼈대 + fake_kompound_env)   ← 병렬, 파일 겹침 없음
                                                    │
Wave 1:                     ┌───────────┬──────────┼──────────┬───────────┐
                          T-3         T-4          T-5        T-6         T-7        ← 5개 병렬 (전부 T-2 의존)
                       (config)  (scan/naming    (git_state) (wt_target  (runtime_state)
                                   /dedup)                    /report)
                            │        │
Wave 2:                     └───┬────┘
                             T-8 (registry/wiki_log)        T-9 (verify)             ← 병렬 (T-3,T-4 의존)
                                  │                              │
Wave 3:                          └──────────────┬───────────────┘
                                             T-10 (apply, 2단 커밋 경계)              ← T-4,T-5,T-8,T-9 의존
                                                  │
Wave 4:                                        T-11 (cli 통합)                       ← 전 코어 의존
                                                  │
Wave 5:                       ┌───────────────────┴───────────────────┐
                           T-12 (stop-pipeline.py 수정)          T-13 (T2 게이트 신규 + hooks.json 등록)
                    [PROTECTED · 사람 승인 필요 · T-1 GREEN 필수]   [PROTECTED · 사람 승인 필요 · T-1 GREEN 필수]
```

> **Wave 배치 근거**: taskmaster tasks-모드 보고 초안을 그대로 채택(변경 없음). 아래 재검증에서 Wave 1 5개 병렬 태스크의 파일 소유권 충돌이 없음을 확인했다.

---

## 파일 소유권 충돌 재검증 (dag 모드, 컨트롤러 지시에 따른 검증)

**Wave 1 (T-3~T-7, 5개 동시 실행) 재검증 결과: 충돌 0건.** 각 태스크의 실 코드 파일과 테스트 파일이 전부 서로 다른 파일명이다(`config.py` / `scan.py`+`naming.py`+`dedup.py` / `git_state.py` / `wt_target.py`+`report.py` / `runtime_state.py` — 대응 테스트 파일도 1:1 고유).

taskmaster tasks-모드 보고에서 지적된 공유 경로 3건은 **전부 다른 Wave 간 순차 관계**이며 동시 실행되는 일이 없다:

| 공유 경로 | 선행(생성) | 후행(수정/재사용) | Wave 간격 | 충돌 여부 |
|---|---|---|---|---|
| `hooks/lib/kompound_snapshot/__init__.py` | T-2 (Wave 0, 최소 스텁만 생성) | T-11 (Wave 4, 공개 API 재노출로 채움) | 4단계 이격 | 없음 — 동시 실행 안 됨 |
| `tests/test_kompound_snapshot_static_imports.py` | T-2 (Wave 0, 정적검사 뼈대 생성) | T-11 (Wave 4, 전 모듈 완비 후 재실행만 — 파일 내용 수정 불필요) | 4단계 이격 | 없음 |
| `tests/fixtures/` (하위 골든 텍스트) | T-2 (Wave 0, `fake_kompound_env` 내장 조각) | T-8 (Wave 2, registry 3형상 골든 필요 시 추가) | 2단계 이격 | 없음 |

**결론**: Wave 내부(동일 Wave, 동시 디스패치) 파일 소유권 충돌 가능성 0건. Wave를 추가로 쪼갤 필요 없음 — 원안(taskmaster 초안) 그대로 확정.

**git 규율(재확인)**: 공유 worktree이므로 각 에이전트는 아래 "파일 소유권" 표의 자기 경로만 `git add <경로>`로 명시 스테이징한다. `git add -A` / `git add .` 금지, 브랜치 전환 금지(`.harness/LEARNING.md` 2026-06-17 엔트리 2건 — 근거).

---

## 현재 진행
- 현재 Wave: 1 (**PAUSED_AT_LIMIT**)
- 완료 Wave: **0** (T-1·T-2 complete, Wave 0 verify TEST_PASS — 스코프 94 / 전체 627 passed / kompound 오염 0 / 재현성 2회 동일)
- **Wave 5 게이트: 충족** (T-1 = complete)

---

## 리밋 시 마지막 상태 (재개용 — 2026-07-29/30)

**중단 사유**: 조직 **월 지출 한도 초과**(`You've hit your org's monthly spend limit`). 태스크 실패가 아니라 외부 한도이며, **3개 에이전트가 동시에 종료**되어 리밋 프로토콜상 전체 리밋으로 판정했다.

**코드 상태**: 전부 커밋됨. tip `530009f`. 미커밋은 이 STATE 파일뿐(오케스트레이터 갱신분). **전체 스위트 844 passed / 0 failed** (기존 533 실패 0 유지).

| 커밋 | 내용 |
|---|---|
| `719b16b` | T-1 회귀 안전망 (82) |
| `561ce12`→`13158b9` | T-2 패키지 뼈대 + fixture (12, it.2) |
| `03d1c4d` | T-3 설정 해석 (19) |
| `a1e0f18` | T-5 git 상태 (25) |
| `7abc271` | T-6 명령 파싱·리포트 (121) |
| `530009f` | T-4 스캔·네이밍·dedup (52) |

**재개 시 해야 할 일 (순서대로)**

1. **T-7 전체 재디스패치** — 유일하게 **구현이 안 된** 태스크다. 에이전트가 모듈을 쓰기 직전(“`config.py`의 `state_max_age_hours` 기본값 확인 후 모듈 작성”)에 종료됐다. 산출물 없음(`runtime_state.py` 미생성).
2. **T-4 compliance 재실행** — 리밋으로 죽었다(판정 없음). 구현·테스트는 완료 상태.
3. **T-5 리뷰 재실행** — 리밋으로 죽었다. **미결 판정 포함**: `check_preconditions()`에 파생 필드(`precondition_failed = not ok or dirty or diverged`)를 추가할지. 오케스트레이터 의견은 "추가하는 쪽이 맞다"(방어선이 docstring 하나뿐 → T-10이 판단식 재구현 중 실수하면 F9 무력화). 리뷰어가 [P1] 동의하면 T-5 iteration 2로 처리.
4. **T-6 리뷰 실행** — 아직 미실행(리뷰어 슬롯 순차 대기 중이었다). compliance는 PASS.
5. **T-3은 검증 완료** — compliance PASS + REVIEW_PASS. Wave 1 일괄 test verify만 남음.
6. Wave 1 전원 complete 후 → **Wave 2**(T-8·T-9) → Wave 3(T-10) → Wave 4(T-11) → **Wave 5**(T-12·T-13, protected · T-1 게이트 이미 충족).

**주의**: Wave 1의 확정 계약(§"T-3 확정 사항" / §"T-4 확정 인터페이스" / §"T-5 확정 계약" / §"T-6 확정 계약")과 §"이월 실행 항목" C-2·C-3은 재개 후 디스패치 프롬프트에 반드시 다시 주입해야 한다 — 그것이 T-10·T-11·T-13 배선의 근거다.

---

## 태스크 상태

| ID | Wave | 구현자 | Status | Iteration | Agent | 비고 |
|----|------|--------|--------|-----------|-------|------|
| T-1 | 0 | sdd-test-automator (refactor) | **complete** | 1 | - | F17 회귀 안전망 `719b16b`. compliance PASS + REVIEW_PASS + Wave0 TEST_PASS. **Wave 5 게이트 충족** |
| T-2 | 0 | sdd-python-engineer | **complete** | 2 | - | 패키지 뼈대 + fixture `561ce12`→`13158b9`(it.2). it.1 [P1] 해소, REVIEW_PASS, TEST_PASS. **§"T-2 확정 사항" 참조** |
| T-3 | 1 | sdd-python-engineer | testing | 1 | Wave1 verify 대기 | `config.py` (F16) — `03d1c4d`, 19 tests. **compliance PASS**(12항목) + **REVIEW_PASS**([P1] 0). **확정 4건은 §"T-3 확정 사항"** |
| T-4 | 1 | sdd-python-engineer | verifying | 1 | **compliance 리밋 사망 → 재실행 필요** | `scan.py`/`naming.py`/`dedup.py` (F3/F4/F5/F12) — `530009f`, 52 tests, 전체 **844 passed 0 failed**. **인터페이스는 §"T-4 확정 인터페이스"**. 리뷰어 슬롯 대기 |
| T-5 | 1 | sdd-python-engineer | verifying | 1 | **리뷰 리밋 사망 → 재실행 필요** | `git_state.py` (F9) — `a1e0f18`, 25 tests, 전체 671 passed. **계약은 §"T-5 확정 계약"**. 리뷰어 슬롯 대기(순차) |
| T-6 | 1 | sdd-python-engineer | verifying | 1 | compliance PASS(18항목) / **리뷰 미실행** | `wt_target.py`/`report.py` (F2 파싱, F11) — `7abc271`, 121 tests. **계약은 §"T-6 확정 계약"**. 리뷰어 슬롯 대기 |
| T-7 | 1 | sdd-python-engineer | **interrupted** | 1 | **리밋 사망 · 산출물 없음 → 전체 재디스패치** | `runtime_state.py` (F1 상태 6종) |
| T-8 | 2 | sdd-python-engineer | pending | 0 | - | `registry.py`/`wiki_log.py` (F7/F10) |
| T-9 | 2 | sdd-python-engineer | pending | 0 | - | `verify.py` (F8) |
| T-10 | 3 | sdd-python-engineer | pending | 0 | - | `apply.py` (F6, (i)/(ii) 커밋 경계) |
| T-11 | 4 | sdd-python-engineer | pending | 0 | - | `cli.py` 통합 (F13 잔여, 정적검사 완결) |
| T-12 | 5 | sdd-python-engineer | pending | 0 | - | **PROTECTED · 사람 승인 필요(F15)**. `stop-pipeline.py` 수정(F1). 게이트: T-1 Status=`complete` 필수 |
| T-13 | 5 | sdd-implementer | pending | 0 | - | **PROTECTED · 사람 승인 필요(F15)**. T2 게이트 신규 + `hooks.json` 등록(F2/F14). 게이트: T-1 Status=`complete` 필수 |

### Status 값
- `pending` — 아직 시작 안 됨
- `implementing` — Engineer Agent가 구현 중
- `reviewing` — Reviewer Agent가 리뷰 중
- `fixing` — Engineer Agent가 리뷰 피드백 반영 중
- `testing` — Test Automator Agent가 검증 중
- `complete` — 완료 (리뷰 + 테스트 통과)
- `interrupted` — 리밋/에러로 중단됨
- `escalated` — 3회 실패, 사용자 개입 필요

---

## 에이전트 배정
- 오케스트레이터: 메인 세션
- Engineer 슬롯 1: idle
- Engineer 슬롯 2: idle
- Engineer 슬롯 3: idle
- Engineer 슬롯 4: idle
- Engineer 슬롯 5: idle (Wave 1이 5개 동시 실행이므로 슬롯 5개 확보)
- Reviewer: idle
- Test Automator: idle

---

## 파일 소유권

| 태스크 | 소유 파일 (정확한 경로 — 디렉토리 와일드카드 금지) |
|--------|-------------------|
| T-1 | `tests/test_stop_pipeline_characterization.py`, `tests/test_hooks_json_contract.py` |
| T-2 | `hooks/lib/kompound_snapshot/__init__.py`, `tests/conftest.py`(fixture 추가분만), `tests/test_kompound_snapshot_static_imports.py` |
| T-3 | `hooks/lib/kompound_snapshot/config.py`, `tests/test_kompound_snapshot_config.py` |
| T-4 | `hooks/lib/kompound_snapshot/scan.py`, `hooks/lib/kompound_snapshot/naming.py`, `hooks/lib/kompound_snapshot/dedup.py`, `tests/test_kompound_snapshot_scan.py`, `tests/test_kompound_snapshot_naming.py`, `tests/test_kompound_snapshot_dedup.py` |
| T-5 | `hooks/lib/kompound_snapshot/git_state.py`, `tests/test_kompound_snapshot_git_state.py` |
| T-6 | `hooks/lib/kompound_snapshot/wt_target.py`, `hooks/lib/kompound_snapshot/report.py`, `tests/test_kompound_snapshot_wt_target.py`, `tests/test_kompound_snapshot_report.py` |
| T-7 | `hooks/lib/kompound_snapshot/runtime_state.py`, `tests/test_kompound_snapshot_runtime_state.py` |
| T-8 | `hooks/lib/kompound_snapshot/registry.py`, `hooks/lib/kompound_snapshot/wiki_log.py`, `tests/test_kompound_snapshot_registry.py`, `tests/test_kompound_snapshot_wiki_log.py`, `tests/fixtures/`(registry 골든 텍스트 추가분만) |
| T-9 | `hooks/lib/kompound_snapshot/verify.py`, `tests/test_kompound_snapshot_verify.py` |
| T-10 | `hooks/lib/kompound_snapshot/apply.py`, `tests/test_kompound_snapshot_apply.py` |
| T-11 | `hooks/lib/kompound_snapshot/cli.py`, `hooks/lib/kompound_snapshot/__init__.py`(재노출로 수정), `hooks/lib/kompound_snapshot/__main__.py`, `tests/test_kompound_snapshot_cli.py` |
| T-12 | `hooks/enforcement/stop-pipeline.py`(PROTECTED), `skills/sdd-orchestrator/SKILL.md`, `tests/test_stop_pipeline_kompound_gate.py` |
| T-13 | `hooks/enforcement/kompound-snapshot-gate.sh`(신규, PROTECTED), `hooks/hooks.json`(PROTECTED), `tests/test_kompound_snapshot_gate_script.py` |

> **명시적 비소유 선언 (오탐 방지, `.harness/LEARNING.md` 2026-07-01 엔트리 근거)**: `docs/sdd/**`(spec/arch/task 문서 자체, 이 STATE 파일 포함), `HANDOFF.md`, `.harness/**`는 **어느 태스크의 소유도 아니다**. `hooks/file-ownership.sh`가 이 STATE의 "## 파일 소유권" 섹션 존재만으로 매칭을 시도해 위 경로들을 오탐한 이력이 있으므로, 이 섹션 밖의 문서 작업(태스크 완료 보고, HANDOFF 작성 등)은 이 표의 매칭 대상이 아님을 여기 명시해 둔다.

> **병렬 git 규율**: 공유 worktree이므로 각 에이전트는 위 소유 파일만 `git add <경로>`로 명시 스테이징. `git add -A` / `git add .` 금지. 브랜치 전환 금지.

---

## T-2 확정 사항 (Wave 0 → 후속 전 태스크가 반드시 따를 것)

T-2가 arch에 없어 직접 결정한 사항이다. **후속 태스크는 이 값을 그대로 쓰고 다시 결정하지 않는다.**

1. **`__init__.py`는 종료 코드 표·런타임 상태 6종을 정의하지 않는다.** arch §11이 각각을 `report.py`(F11 → **T-6**)와 `runtime_state.py`(F1 → **T-7**) 소관으로 지정했으므로 값의 단일 진실은 그 두 모듈이다. `__init__.py`는 소유 모듈만 문서화한다.
2. **정적 검사의 허용 non-stdlib 최상위 루트 = `{"hooks"}`** — arch §4의 유일한 허용 의존(`kompound_snapshot` 자기 참조 + `hooks.lib.self_improve.state_io` 단방향 재사용)을 커버. 모듈이 늘어도 이 검사가 깨지지 않도록 세분화하지 않았다.
3. **절대경로 리터럴 금지 정규식은 `/Users/`·`/home/`로 한정**(spec F16 예시 그대로). 모든 `/` 시작 문자열을 금지하면 docstring 예시까지 오탐하므로 범위를 좁혔다.
4. **`fake_kompound_env` 골든 텍스트 구체값** — registry 3형상 프로젝트명 `acme-widget`/`beta-service`/`gamma-tool`, 스냅샷 집합 raw 6개 + **경계 케이스 1개** `notaproject-standalone-topic-ui.md`(prefix `notaproject`는 `prefix_map.values()` 밖 — 실제 kompound의 미링크 5건에 대응). 카운트 문장 2종은 실제 registry 문구 형식을 복제: `"N feature · raw M개(spec X · arch Y · result Z · api W · ui V · context U)."` 와 `` "- raw: `raw/<project>-<feature>-<kind>.md` M개 (위 표 링크)" ``.
   → **T-8**(`registry.py`/`wiki_log.py` 소유)이 arch §6.3.3 화이트리스트 정규식을 짤 때 이 두 리터럴 패턴을 기준으로 삼는다. (T-2 보고가 이를 "T-9"로 지칭했으나 `registry.py` 소유자는 **T-8**이다 — 파일 소유권 표 기준.)
5. **fixture의 repo 디렉토리명 = `prefix_map`의 키와 정확히 일치**(arch §5.4.2 `repo_dir` 조회 계약과 정합).
6. **git identity는 로컬 `-c` 플래그로만 주입**(`user.email`/`user.name`/`commit.gpgsign=false`) — 전역/리포 config 무변경. **T-5**(`git_state.py`)·**T-10**(`apply.py` 커밋)도 이 방식을 따른다.

### T-3 확정 사항 (Wave 1 — 후속 태스크가 따를 것)

1. **`DEFAULT_PREFIX_MAP`은 `config.py`가 보유한다** — arch §6.1은 `naming.py` 상수를 제안했으나, T-3·T-4가 **동시 병렬 구현**이라 서로의 미생성 모듈을 import하면 레이스가 된다. `config.py`가 `prefix_map` 병합의 최하위 소스로 이 상수를 가져야 하는 구조적 필요도 있다. → **T-4의 `naming.py`는 자체 재정의하지 말고 `from hooks.lib.kompound_snapshot.config import DEFAULT_PREFIX_MAP`으로 재사용**하거나 인자로 주입받는다. **T-11이 통합 시 중복 정의 여부를 반드시 재확인**한다.
2. **`HARNESS_KOMPOUND_CONFIG`로 로드된 값의 `source` 태그 = `"project"`** — 라벨 집합을 `env|project|home|discovery` 4종으로 고정 유지(새 라벨 미추가).
3. **`prefix_map`의 `source` = `"default"` 또는 `"merged"`** — 개별 키 단위 출처가 아니라 요약 2값. 스칼라처럼 단일 소스 라벨이 성립하지 않기 때문.
4. **`ok` 필드 의미 = `(kompound_repo is not None)`** — 내부 예외도 동일 모양(`ok: False`, `kompound_repo: None`)으로 흡수하고 진단용 `error` 키만 추가. 선언된 7키 스키마 유지.

### T-5 확정 계약 (`git_state.py` — T-10·T-13이 의존)

공개 함수: `check_dirty` / `check_divergence` / `check_preconditions`(T-10 진입점) / `commit_raw` / `commit_catalog` / `acquire_lock` / `release_lock`

> ⚠️ **`ok`의 의미를 오해하면 F9가 무력화된다.** `ok`는 **"판정이 기술적으로 정상 수행됐는가"**이지 "선행조건 통과"가 **아니다**. `dirty=True`/`diverged=True`여도 `ok=True`일 수 있다.
> **호출자(T-10·T-13)는 반드시 `not ok or dirty or diverged` 가 참이면 F9 `precondition_failed`로 처리한다.**
> `reason`: `ok=False`→오류 메시지 / `ok=True`+dirty|diverged→`"dirty"`|`"diverged"`(dirty 우선) / 그 외 `None`.

- `commit_raw(...)` 메시지 `snapshot(raw): N new, M updated` / `commit_catalog(...)` 메시지 `snapshot(catalog): {detail}` — **(i)/(ii) 독립 2단 커밋**(A-5 커밋 경계 구현체).
- 커밋할 변경 없음은 에러 아님 → `committed=False, reason="no_changes"`.
- `acquire_lock`은 `busy` / `stale_lock_reclaimed` 반환 — **T-6의 `exit 70 busy`와 대응**. T-11 통합 시 두 계약이 맞물리는지 확인할 것.
- `fetch`/`pull`/`push` 문자열 부재를 정적 테스트로 고정(F13 네트워크 무호출).
- `commit_raw`/`commit_catalog`/`acquire_lock`/`release_lock`은 **스코프 침범이 아니다** — arch §3.2(L125)·§9.1(L796)이 `git_state` 계약에 커밋 결과·락 파일을 명시적으로 포함한다(T-5 compliance 확인).
- **미결(오케스트레이터 판단)**: compliance가 `check_preconditions()`에 파생 필드(`precondition_failed = not ok or dirty or diverged`) 추가를 권고했다. arch 위반이 아니라 FAIL은 아니지만, 현재 방어선이 docstring 하나뿐이어서 T-10이 판단식을 재구현하다 틀리면 F9가 조용히 무력화된다. → **T-5 리뷰 피드백과 합쳐 iteration 2에서 처리 예정.**

### T-6 확정 계약 (`report.py`/`wt_target.py` — T-10·T-11·T-13이 의존)

**종료 코드 상수** (단일 진실 = `report.py`):
`EXIT_OK=0` `EXIT_PENDING=10` `EXIT_DISABLED=20` `EXIT_SCAN_ERROR=30` `EXIT_PRECONDITION_FAILED=40` `EXIT_UNMAPPED_BLOCKING=45` `EXIT_VERIFY_FAILED=50` `EXIT_CATALOG_UNPARSED=55` `EXIT_WRITE_FAILED=60` `EXIT_BUSY=70`

**verdict 12종** (`unmapped_in_target` 폐기 반영): `ok_no_pending`/`snapshotted`/`no_target`/`pending`/`disabled`/`scan_error`/`precondition_failed`/`unmapped_blocking`/`verify_failed`/`catalog_unparsed`/`write_failed`/`busy`

**단계 필드 = `stage`** — `STAGE_NONE`/`STAGE_SCAN`/`STAGE_PRECONDITION`/`STAGE_LOCK`/`STAGE_RAW`(=(i))/`STAGE_CATALOG`(=(ii)). 조회 `report.stage_for_verdict(verdict)`.

> 📌 **T-13은 정책을 재유도하지 마라.** `report.blocks_deletion(verdict) -> bool`이 A-5 정책을 **이미 계산**한다: `write_failed`·`scan_error`·`precondition_failed`·`unmapped_blocking`·`busy` → `True`(차단) / `verify_failed`·`catalog_unparsed` → `False`(경고 후 통과) / 정상·비활성 → `False`. `report.VERDICT_TABLE[verdict]`가 `{exit_code, stage, blocks_deletion}` 3필드를 모두 담는다.

기타 공개 API: `build_report()` / `build_inherited_warning(runtime_status, *, reason, catalog_lag_count)` / `build_human_text()` / `emit_report(report_dict, *, json_mode, ...)` / `pending_unmapped_disjoint()`.
`wt_target`: `find_worktree_removal_targets(command, *, cwd=None)` / `is_worktree_path(path)`. 판정은 `.git`이 `gitdir:` 파일(강신호) 또는 `worktrees/` 세그먼트+디렉토리(잔해)만 — **이름 기반 판정 없음**. 승인된 미탐 5종을 테스트로 명시 고정.

### ~~감시 항목 (Wave 1 병렬 과도 상태)~~ — **해제됨**

- T-6 시점 전체 스위트 834 passed / **3 failed**(전부 `tests/test_kompound_snapshot_naming.py`, T-4 소유·당시 진행 중)였다. → **T-4 완료 시점 844 passed / 0 failed로 해소 확인.** 병렬 진행 중의 과도 상태였고 T-6 소유 파일과 무관했다.

### T-4 확정 인터페이스 (T-11 배선 필수)

- `scan(scope_roots, max_anchor_depth)` → `{"records", "anchors", "errors"}`
- `derive_repo_dir(...)` — arch §5.4.2 규칙 1~4 + `gitdir:` 파싱
- **`name_document(record, prefix_map, scan_root=None)`** — `prefix_map`이 **필수 파라미터**다. T-4는 `config.py`를 import하지 않았고 자체 정의도 하지 않았다(병렬 레이스 회피 + task 지시 준수). 값은 `config.DEFAULT_PREFIX_MAP`과 정확히 일치 확인됨(10 distinct prefix / 14 repo 키).
- → **T-11은 호출 시 `config.resolve_config()["prefix_map"]`을 명시적으로 전달**해야 한다. `naming.py`가 `config`의 기본값을 자동 재사용하지 않으므로 배선 누락 시 조용히 잘못된 프리픽스가 나올 수 있다. T-3 확정 사항 #1의 "T-11 재확인" 항목이 이것으로 확정됐다.
- `resolve_prefix`는 1차 조회 실패 시 **scan_root 기준 완화 재조회**를 한다(arch J-9 폴백).

### 이월 실행 항목 (T-2 compliance 관찰사항 — 담당 태스크가 처리한다)

| # | 내용 | 담당 |
|---|------|------|
| C-1 | 정적 검사의 허용 non-stdlib 루트가 `{"hooks"}`로 **arch §4보다 느슨하다**(§4는 `hooks.lib.self_improve.state_io` 단방향만 허용). → **T-2 리뷰에서 [P1]로 격상**(주석은 좁게 주장하는데 로직은 `hooks.*` 전체를 통과시켜, 후속 10개 태스크의 유일한 자동 아키텍처 가드가 무력). **T-3으로 이월하지 않고 T-2 iteration 2에서 해소**한다. | ~~T-3~~ → **T-2 (it.2)** |
| C-3 | **import 스타일 지침 (T-3~T-11 전원)**: `from hooks.lib.self_improve import state_io` 형태는 정적 검사가 `dotted="hooks.lib.self_improve"`로 읽어 **위반으로 오탐**한다. 반드시 `from hooks.lib.self_improve.state_io import <X>` 형태를 써라(이 레포 기존 관례와 동일). T-2 리뷰 논-P1 관찰. | **T-3~T-11** |
| C-2 | F16 절대경로 리터럴 정규식이 `/Users/`·`/home/`만 잡는다. spec F16 문언은 충족하나 arch §2.2의 "Windows(Git-bash)에서 깨지지 않아야 한다" 제약을 감안하면 `C:\Users\...` 같은 Windows 스타일 리터럴은 못 잡는다. **최종 정적 게이트를 완결하는 T-11에서 패턴 확장 여부를 판단·처리한다.** | **T-11** |

---

## 중요 제약 (Engineer/Reviewer/Test-Automator 공통 전달)

1. **Wave 0 게이트(F17)**: T-1(회귀 안전망)이 `complete`가 아니면 Wave 5(T-12/T-13)는 시작하지 않는다. Wave 1~4는 이 게이트와 무관하게 정상 진행한다.
2. **protected set(F15)**: T-12, T-13은 `hooks/enforcement/`(디렉토리 전체) 및 `hooks/hooks.json`을 건드리므로 CLAUDE.md protected set이다. **자동 승격 경로(self-improve) 불가, 사람 승인 필수.** 이 사이클은 사용자가 이번 대화에서 명시적으로 지시하여 승인 조건을 충족했다(spec F15) — result 문서와 PR 설명에 "하네스 티어 / 사람 승인 완료" 표기가 반드시 있어야 머지 가능하다.
3. **단일 판정 구현 원칙(arch §1)**: 스캔·네이밍·dedup·멱등·검증 로직은 `hooks/lib/kompound_snapshot/` 코어에만 존재한다. T-12(stop-pipeline.py)는 코어를 in-process import, T-13(bash 게이트)는 서브프로세스로 호출한다 — bash에 판정 로직을 복제하지 않는다.
4. **결정↔판단 분리 + fail-safe**: 코어 패키지(`hooks/lib/kompound_snapshot/`)는 Python stdlib-only, 네트워크/LLM 무호출, 모든 함수가 예외를 던지지 않고 구조화된 dict를 반환한다.
5. **TDD 순서**: T-1은 test-automator **refactor 모드**(현재 동작 고정, 스펙 아님) — tdd 모드와 구분. 그 외 전 태스크는 표준 RED(test-automator) → GREEN(engineer) 순서.
6. **fast-scoped 빌드 프로파일**: 워밍업 빌드 없음. 태스크당 `PATH="/opt/homebrew/bin:$PATH" python3 -m pytest <스코프> -q`만 실행. no-clean(`__pycache__`/`.pytest_cache` 보존).
7. **git 규율**: 공유 worktree 병렬 실행 — 소유 파일만 명시적 `git add`, `git add -A`/`.` 금지, 브랜치 전환 금지(§"파일 소유권" 참조).
8. **spec/arch에 없는 설계 결정 임의 변경 금지**: 환경변수 이름(`HARNESS_KOMPOUND_REPO` 등), 설정 파일 위치, CLI 서브커맨드(`check`/`apply`/`gate`), 종료 코드 표(0/10/20/30/40/45/50/55/60/70), 상태 값 6종, `snapshot_set_rule`, registry 표 탐색 3단은 arch에서 이미 확정됨 — task 문서에 인용된 값을 그대로 구현한다.

---

## 이력
- [2026-07-29] ORCHESTRATOR_STATE.md 초기 생성 (dag 모드) — 13개 태스크, Wave 0~5 구성 확정(taskmaster tasks-모드 초안 그대로 채택), Wave 1 파일 소유권 충돌 재검증 완료(충돌 0건), 빌드 프로파일 메타 이식, Wave 0 게이트(F17) 실행 규칙 명시, 팀 배정 섹션 생략(단일 오케스트레이터 모드). 상태 PLANNING.
