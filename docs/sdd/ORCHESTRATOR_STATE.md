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
- 상태: **COMPLETED** (2026-08-04) — 13/13 태스크 complete, 통합 검증 PASS, result 문서 작성. 머지는 사람 승인 대기.
- 이력: EXECUTING (**2026-08-04 재개** — 리밋 2차 해제 후 `/sdd resume`. T-11 산출물은 에이전트 종료 전 전부 생성돼 있었고 오케스트레이터가 검증 후 `b03e096`으로 커밋. / 2026-07-30 1차 재개 — 리밋 해제 후 `/sdd resume`. 재개 전 확인: tip `60e41f0`, 워킹트리 clean, 전체 844 passed / 0 failed, `runtime_state.py` 부재 확인)
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
- 현재 Wave: **전 Wave 완료 · 통합 검증 PASS · result 문서 작성 완료** → 머지 승인 대기
- 완료 Wave: **0, 1, 2, 3, 4, 5 (전부)**
  - Wave 0 verify TEST_PASS — 스코프 94 / 627 passed / 오염 0 / 재현성 2회
  - Wave 5 verify TEST_PASS — 스코프 **85** / **1065 passed 0 failed** / **T-1 안전망 82 passed** / **실제 Stop 훅 실행: stdout 정확히 1줄 유효 JSON(프로토콜 무결)** / **실제 T2 게이트: `rm -Rf` 대문자가 프리필터 통과해 코어 기동 확인(HARNESS_DEBUG=1)** / 격리 7항목 무오염 / 재현성 2회
  - Wave 4 verify TEST_PASS — 스코프 **55** / **1015 passed 0 failed** / CLI 3서브커맨드 실제 실행(예약코드 1·2 없음, stdout 유효 JSON) / 격리 무오염 / 재현성 2회
  - Wave 3 verify TEST_PASS — 스코프 **11** / **972 passed 0 failed** / 격리 7항목(kompound `git log` 전후 동일=새 커밋 없음 · `raw/` 230개 불변 포함) / 재현성 2회
  - Wave 2 verify TEST_PASS — 스코프 **79** / **961 passed 0 failed** / 격리 5항목(위키 3파일 md5·size·mtime 전후 완전 동일 포함) / 재현성 2회 동일
  - Wave 1 verify TEST_PASS — 스코프 **255** / **882 passed 0 failed** / 격리 4항목(kompound·실제 홈·런타임 상태파일·잔여물) 전부 무오염 / 재현성 2회 동일
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
| T-3 | 1 | sdd-python-engineer | **complete** | 1 | Wave1 verify 대기 | `config.py` (F16) — `03d1c4d`, 19 tests. **compliance PASS**(12항목) + **REVIEW_PASS**([P1] 0). **확정 4건은 §"T-3 확정 사항"** |
| T-4 | 1 | sdd-python-engineer | **complete** | 2 | Wave1 verify 대기. it.2 `a90fb10` — compliance PASS + **REVIEW_PASS**(8케이스 직접 실행 검증) | `scan.py`/`naming.py`/`dedup.py` (F3/F4/F5/F12) — `530009f`, 52 tests, 전체 **844 passed 0 failed**. **인터페이스는 §"T-4 확정 인터페이스"**. 리뷰어 슬롯 대기 |
| T-5 | 1 | sdd-python-engineer | **complete** | 3 | Wave1 verify 대기. it.3 `b8c43c9` — 27 tests. **REVIEW_PASS**([P1] 3건 해소, 반환 지점 8개 전수 확인 — 잔존 경로 없음) | `git_state.py` (F9) — `a1e0f18`, 25 tests, 전체 671 passed. **계약은 §"T-5 확정 계약"**. 리뷰어 슬롯 대기(순차) |
| T-6 | 1 | sdd-python-engineer | **complete** | 1 | Wave1 verify 대기 | `wt_target.py`/`report.py` (F2 파싱, F11) — `7abc271`, 121 tests. **계약은 §"T-6 확정 계약"**. 리뷰어 슬롯 대기 |
| T-7 | 1 | sdd-python-engineer | **complete** | 1 | Wave1 verify 대기. `19a8f8e` — 35 tests. compliance PASS(15항목) + **REVIEW_PASS**(파서 실제 STATE 파일 실행 검증, 영구 block 경로 없음) | `runtime_state.py` (F1 상태 6종) |
| T-8 | 2 | sdd-python-engineer | **complete** | 2 | Wave2 verify. it.2 `627da7f` — compliance PASS + REVIEW_PASS(실제 index.md read-only 검증) | `registry.py`/`wiki_log.py` (F7/F10) |
| T-9 | 2 | sdd-python-engineer | **complete** | 1 | Wave2 verify 대기. `f7b3ed8` — 41 tests. compliance PASS(15항목) + **REVIEW_PASS**(실제 registry 전수 확인·경계 케이스 추적) | `verify.py` (F8) |
| T-10 | 3 | sdd-python-engineer | **complete** | 3 | - | `c5cca64`→`5070ac3`(it.2)→`b8f0170`(it.3), 11 tests. compliance PASS + REVIEW_PASS + TEST_PASS. `apply.py`는 it.2·it.3에서 0줄 변경(테스트만 보강) | `apply.py` (F6, (i)/(ii) 커밋 경계) |
| T-11 | 4 | sdd-python-engineer | **complete** | 1 | Wave4 verify. `b03e096` — 55 스코프. compliance PASS(22항목) + **REVIEW_PASS**([P1] 0, 테스트 독립 재현) | `cli.py` 통합 (F13 잔여, 정적검사 완결) |
| T-12 | 5 | sdd-python-engineer | **complete** | 3 | Wave5 verify 대기. `b41d8e4`→`a59480f`(it.2)→`1599672`(it.3) — 19 tests. compliance PASS + **REVIEW_PASS**([P1] 3건 해소: 문서 stale·영구 스캔 비용·baseline 오손) | **PROTECTED · 사람 승인 필요(F15)**. `stop-pipeline.py` 수정(F1). 게이트: T-1 Status=`complete` 필수 |
| T-13 | 5 | sdd-implementer | **complete** | 2 | Wave5 verify 대기. `8e6a55c`→`01097a6`(it.2) — 31 tests. compliance concerns 2건 해소 + **REVIEW_PASS**(shopt 스코프·과다매칭·jq 파싱·성능 전부 확인) | **PROTECTED · 사람 승인 필요(F15)**. T2 게이트 신규 + `hooks.json` 등록(F2/F14). 게이트: T-1 Status=`complete` 필수 |

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
| T-2 | `hooks/lib/kompound_snapshot/__init__.py`, `tests/conftest.py`(fixture 추가분만), `tests/test_kompound_snapshot_static_imports.py` — ⚠️ **후자 2개는 Wave 4에서 T-11로 위임됨**(`__init__.py`=공개 API 재노출 / 정적검사=이월 C-2 패턴 확장). Wave 0 완료 후이므로 병렬 충돌 없음 |
| T-3 | `hooks/lib/kompound_snapshot/config.py`, `tests/test_kompound_snapshot_config.py` |
| T-4 | `hooks/lib/kompound_snapshot/scan.py`, `hooks/lib/kompound_snapshot/naming.py`, `hooks/lib/kompound_snapshot/dedup.py`, `tests/test_kompound_snapshot_scan.py`, `tests/test_kompound_snapshot_naming.py`, `tests/test_kompound_snapshot_dedup.py` |
| T-5 | `hooks/lib/kompound_snapshot/git_state.py`, `tests/test_kompound_snapshot_git_state.py` |
| T-6 | `hooks/lib/kompound_snapshot/wt_target.py`, `hooks/lib/kompound_snapshot/report.py`, `tests/test_kompound_snapshot_wt_target.py`, `tests/test_kompound_snapshot_report.py` |
| T-7 | `hooks/lib/kompound_snapshot/runtime_state.py`, `tests/test_kompound_snapshot_runtime_state.py` — ⚠️ **Wave 5에서 `runtime_state.py`(+대응 테스트)를 T-12로 위임**(성능 [P1] 수정: 무장 여부만 싸게 판정하는 헬퍼 노출. 판정 로직을 `stop-pipeline.py`에 복제하지 않기 위함). T-7 완료 후이므로 병렬 충돌 없음 |
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
> **→ it.2(`9f5b6cc`)에서 결합 필드 `precondition_failed`(= `not ok or dirty or diverged`)가 추가됐다. T-10·T-13은 판단식을 재조립하지 말고 이 필드를 써라.**
> (원 계약 유지: 개별 필드도 그대로 있다. additive 변경.)
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

### 🔴 설계 공백 D-impl-1 — CATALOG_PENDING 재시도 시 registry 링크 영구 누락 (오케스트레이터 결정)

**발견**: T-8 compliance(항목 20). **T-8 파일 자체는 무결**이고 결함은 arch의 분류 체계에 있다.

**경로**: ①1차 실행에서 문서가 F6상 `new` → raw 커밋 성공 → (ii) 카탈로그 실패(`CATALOG_PENDING`) ②2차 재시도에서 raw가 이미 존재·내용 동일 → **F6이 `unchanged`로 재분류** ③`update_registry`의 계약이 `new_docs`="새로 생성된 문서만"이므로 이 문서는 **어떤 재시도에서도 `new_docs`에 못 들어감** → **registry에 영구 미링크**. 경고도 없다(F11 정신 위반).

**근본 원인**: arch §6.2 `raw_stage` 스키마가 `"new": [], "updated": [], "unchanged": N` — `unchanged`를 **카운트로만** 두고 목록화하지 않는다. F6의 내용 기반 분류축이 "카탈로그 미링크"를 별도 차원으로 추적하지 않는 구조적 공백.

**결정 (오케스트레이터, 2026-07-30)**: **새 상태를 영속화하지 않고 registry에서 도출한다.**
- T-9 `verify.py`가 게이트(2)에서 이미 `missing_links = snapshot_population(raw) - snapshot_registry_links(registry)`를 계산한다. **이 집합이 정확히 "raw는 있는데 registry가 링크하지 않은 문서"다.**
- → **`new_docs`의 의미를 "이번 F6 분류상 new"에서 "카탈로그 링크가 아직 없는 문서 전체"로 재정의**한다.
- 장점: 추가 상태 없음 / **자기 치유적**(재시도 횟수 무관, 언제 끊겼든 다음 실행이 복구) / 사람이 수동으로 넣은 raw까지 커버 / 기존 T-9 함수 재사용.
- **T-8 조치(it.2)**: `registry.py`의 계약 docstring을 이 의미로 재정의 + "unchanged로 분류됐지만 미링크인 문서가 행을 얻는다"는 테스트 추가. 로직 변경은 사실상 불필요(순수 함수는 받은 목록을 쓴다).
- **T-10 조치**: `new_docs`를 F6 분류가 아니라 `verify.snapshot_population(...) - verify.snapshot_registry_links(...)`로 계산해 전달. **T-10 리뷰의 필수 확인 항목.**
- **arch 수정 항목**: §6.2 `raw_stage` 스키마와 §6.3.0 재시도 서술에 이 도출 방식을 명시(result 문서에 반영).

### ⚠️ T-11 진행 특이사항 (검증 시 참고)

**T-11 에이전트가 외부 지출 한도로 2회 종료**되어 **최종 보고를 남기지 못했다**. 산출물은 전부 생성된 상태였고 오케스트레이터가 직접 검증 후 커밋했다:
- 오케스트레이터 검증: 스코프 테스트 `test_kompound_snapshot_cli.py` + `test_kompound_snapshot_static_imports.py` → **55 passed** / 전체 스위트 → **1015 passed 0 failed**(972 → +43) / 커밋 `b03e096`(5파일, +1652/-9).
- **미보고 항목**: ①CLI 인자 스펙·종료코드 매핑 ②**C-2 판단**(절대경로 정적 검사 Windows 패턴 확장 여부 — `test_kompound_snapshot_static_imports.py`가 38줄 변경됐으므로 뭔가 조치된 것으로 보인다) ③**C-5 판단**(`report.RUNTIME_STATUSES` ↔ `runtime_state.STATUSES` import 교체 여부) ④정적 검사 위반 모듈 유무 ⑤arch 없이 직접 결정한 것 ⑥`gate` 5분기가 `blocks_deletion()`과 일치함의 확인 방법.
- → **compliance·리뷰가 diff에서 이 항목들을 역으로 판정**해야 한다. 구현자 보고에 의존할 수 없다.

### T-11 확정 계약 (compliance가 diff에서 복원 — 구현자 미보고분)

- **CLI**: `python3 -m hooks.lib.kompound_snapshot {check|apply|gate}` (`cli.py:387-415` parser). `main()`은 `SystemExit` 재전파, 그 외 예외는 `report.EXIT_SCAN_ERROR`(30)로 흡수 — **크래시 없음**. 리터럴 exit code 0건(전부 `report.py` 상수).
- **`check`** — 부작용 없음(`scan`·`dedup`·`_dry_run_pending` read-only만, `apply` 미호출).
- **`gate`** — 5개 조기 분기(`no_target`/`disabled`/`scan_error`/`unmapped_blocking`/`ok_no_pending`) 후 `precondition_failed` 확인 → `apply` 위임. **`pending`(exit 10) verdict는 `check`에만 존재**.
- **정책 위임 구조(중요)**: `cli.py`는 `blocks_deletion()`을 **직접 호출하지 않는다**. T-11의 책임은 **verdict → exit_code 매핑이 `report.VERDICT_TABLE`과 정확히 일치**하는 것이고(`_map_apply_result_to_verdict` `cli.py:302-328`), 최종 차단/통과 판정은 **T-13(bash 게이트)이 exit code로부터 `blocks_deletion()`을 조회**하는 몫이다. → **T-13은 반드시 `report.blocks_deletion()`을 조회해야 한다**(exit code를 보고 자체 판단하면 A-5가 갈린다).
- **복원된 설계 결정**: `runtime_state.should_emit_unconfigured_notice()`를 **`gate`만 호출**하고 `check`/`apply`는 호출하지 않는다 — 부작용 회피 + 매 Bash 명령마다 안내가 반복되는 소음 방지(F16 취지).
- **C-2 처리**: 절대경로 정적 검사 정규식을 `[A-Za-z]:\\Users\\...`(백슬래시형)으로 **확장**. forward-slash형(`C:/Users/...`)은 기존 패턴이 부분일치로 이미 잡음을 별도 테스트로 검증. 기존 docstring 예시 오탐 없음도 회귀 고정. arch §2.2 대응 최소 확장.
- **C-5 처리(정정)**: `report.py` **미수정**이고, 실제 해소는 **`cli.py._read_runtime_status`가 `runtime_state.STATUSES`(정본)를 직접 참조**하는 것이다(`report.RUNTIME_STATUSES`가 아니라). 두 사본 위험을 CLI 레벨에서 회피했고 arch §4 의존 방향도 보존된다.
- **`check`의 pending 판정은 `apply.py` F6 규칙의 read-only 재구현**(`_dry_run_pending`) — `apply`의 write 로직이 private이고 arch에 read-only F6 변형이 없어 불가피한 중복. docstring에 의도적 중복임이 명시돼 있다. (T-10의 `_decompose_raw_name`과 같은 성격의 코어 내부 중복 — arch §1 문언 범위 밖.)
- **`gate`의 T1→T2 승계 경고 소비**는 `runtime_state`의 6값 스키마 **밖** CLI-private 키(`t2_inherited_consumed_status`)로 추적한다 — T1의 `status` 필드를 변형하면 T1의 재차단 로직이 깨지므로 의도적으로 분리.
- **stdout 오염 없음(검증됨)**: 패키지 12모듈 전체에서 stdout에 쓰는 곳은 **`report.emit_report` 한 곳뿐**(grep 확인). traceback은 stderr로만 나간다.
- `__init__.py`의 삭제 9줄은 "하위 모듈 없음" placeholder + `__all__: list[str] = []`뿐 — **fail-safe 규약·12모듈 표·의존 방향 문단은 보존**.

### Wave 5 진입 실증 (2026-08-04)

- **Wave 0 게이트 충족**: T-1 Status = `complete`(회귀 안전망 82 tests GREEN, compliance+리뷰+verify 전부 통과).
- **사람 승인 충족**: §"사용자 승인 기록" — 사용자가 Wave 0~5 전체 실행을 명시 승인(protected set 포함).
- **T2 대상 식별 실증**: 오케스트레이터가 CLI를 직접 실행해 확인 — 존재하지 않는 경로(`/tmp/foo`)는 `no_target`(사실 기반 판정상 정답), **실제 워크트리 경로는 `no_target`을 지나 `disabled`로 진행**(kompound 미설정 때문) → arch §5.2.3 분기 순서(`no_target → disabled → …`)가 정확히 동작. 우리 워크트리의 `.git`은 `ASCII text`(=`gitdir:` 파일)임을 `file`로 확인.

### T-12/T-13 확정 계약 (Wave 5 — PROTECTED)

**T-12 (`b41d8e4`)** — `stop-pipeline.py`(PROTECTED) + `skills/sdd-orchestrator/SKILL.md` + 13 tests
- 게이트 위치: `decide()` **Step 0 직후 / Step 1 이전**("Step 0.5", L505-512). 정의는 L369-487. **`pipeline.json` 미접근**(인자는 `stop_data`·`project_dir`뿐).
- `DIRECTIVES["PHASE4_KOMPOUND_SNAPSHOT_PENDING"]`(L188-195) — `@@CLI@@`/`@@SCOPE@@` 토큰을 `str.replace`로 치환.
- 부트스트랩: `_resolve_kompound_plugin_root()`(L57-61) `CLAUDE_PLUGIN_ROOT` 우선 → `parents[2]`. `sys.path`에 없을 때만 insert(L64-66). 실제 import는 게이트 함수 내부 지연(L445-447).
- `increment_breaker` **미사용** — 예산은 `runtime_state`가 `.claude/state/kompound-snapshot.json`에 독립 관리(`KOMPOUND_MAX_BLOCKS=3`), `CB_MAX_BLOCKS=20`과 상태 미공유.
- SKILL.md: 박제 스텝 **L166** < self-improve 헤딩 **L180** (spec F1 Acceptance 충족).
- **직접 결정 3건**: ①`cli.py check`가 `project_root` 인자를 안 받고 `CLAUDE_PROJECT_DIR`로 재계산하므로, 게이트가 호출 직전 그 env를 `project_dir`로 설정하고 `finally`에서 원복(L411-423) ②**`cli.main()`이 실제 stdout에 쓰므로** Stop 훅의 "stdout 한 줄 JSON" 규약과 충돌 → `redirect_stdout/stderr` + `StringIO`로 흡수 후 캡처 JSON만 파싱(오염 0) ③핵심 대칭 케이스는 실제 경로, 세부 상태 전이는 monkeypatch로 격리.

**T-13 (`8e6a55c`)** — `hooks/enforcement/kompound-snapshot-gate.sh`(신규, PROTECTED) + `hooks/hooks.json`(PROTECTED) + 23 tests
- **`blocks_deletion()` 조회 방식(A-5 준수 증명)**: JSON에서 `verdict`만 뽑아 **별도 python 원라이너에 argv로 전달**해 `report.blocks_deletion(verdict)`를 조회. **bash는 verdict 목록을 어디에도 나열하지 않는다.** `report.build_report()` JSON 스키마에 `blocks_deletion` 필드가 없음을 먼저 확인해 이 방식이 필요했다. 조회 실패(`0`/`1` 둘 다 아님) 시 **보수적 차단**(fail-safe).
- `hooks.json`: `PreToolUse`/`Bash` 배열 **마지막(6번째)**. 기존 5개 순서 보존(오케스트레이터도 직접 확인).
- 프리필터: `case "$COMMAND" in *worktree*remove*|*rm\ -r*|*rm\ -f*|*--recursive*) ;; *) exit 0 ;; esac` — 텍스트 검사만, 사실 판정 없음. **무관 명령에서 python3 미기동을 센티널 스크립트로 실측**.
- `PYTHONPATH`: 스크립트 자기 위치 기준 `$SCRIPT_DIR/../..`(플러그인 루트). `CLAUDE_PROJECT_DIR`/`HARNESS_PROJECT_ROOT`를 쓰지 않은 이유 = 그건 "프로젝트"이고 설치형 배포에서 코어 코드 물리 위치와 다를 수 있다.
- **직접 결정**: 통과 경로 메시지는 코어의 `human` JSON 필드를 재사용(bash가 새 문구를 만들지 않음) / `gate`가 반환할 수 없는 종료 코드(10·1·127 등) 감지 시 "계약 위반"으로 경고 후 통과(arch §5.2.3 "그 외" 분기를 화이트리스트 `case`로) / python stderr는 버림(정보가 JSON 필드로 동일하게 온다).

### 🟡 후속 태스크 (이 사이클 범위 밖 — 사용자 승인 필요)

- **`__init__.py`의 즉시 전체 re-export가 arch §2.3 성능 예산을 실측상 2배 초과시킨다.**
  - **발견**: T-12 리뷰(it.3)가 **콜드 프로세스**로 실측. `bare python3 -c pass` 36.6ms / `+ import runtime_state` 72.8ms(**패키지 임포트 순수 비용 +36.2ms**) / `decide()` STATE 없음 54.5ms / `decide()` STATE=EXECUTING(무장 안 됨) 97.9ms(**게이트 한계비용 +43.5ms**). arch §2.3 "무장 안 됨 <20ms"를 **2배 이상 초과**.
  - **원인**: `hooks/lib/kompound_snapshot/__init__.py`(T-11 소유)가 12모듈을 **즉시 re-export**한다. Python 임포트 의미론상 **어떤 서브모듈을 import하든 부모 `__init__.py`가 먼저 실행**되므로 "`runtime_state`만 지연 import"로는 회피 불가.
  - **T-12 결함이 아님**: iteration 1의 최초 게이트도 동일하게 12모듈 전부를 로드했다. it.2/it.3이 없앤 것은 **워크스페이스 크기에 비례해 무제한 커지는 `cli.main()` 스캔 비용**이고 그건 정확히 고쳐졌다(`cli.main` 0회 단정 3곳 전부 유지 확인). 임포트 세금은 **고정 ~36ms**로 성격이 다르다.
  - **수정 경로**: `__init__.py`를 **PEP 562 지연 `__getattr__` 기반 re-export**로 전환. 12모듈과 신규 532개 테스트의 임포트 의미론에 영향을 주므로 **별도 사이클로 분리**한다(사이클 막바지에 검증 완료 파일의 임포트 의미론을 바꾸는 것은 시퀀싱이 나쁘다 — 오케스트레이터 판단).
  - **현재 영향**: 정확성 결함은 아니다. Stop 훅마다 ~43ms 고정 지연.

### 통합 검증 결과 (Step 3, 2026-08-04) — PASS

- **F1~F17 전수 충족**. 실측 근거: F8 registry **117 = raw 117, 양방향 차집합 0** / F9 실제 `dirty_files=["wiki/log.md"]` 감지 / F17 안전망 **82 passed**.
- **실제 kompound 관통(dry-run, 읽기 전용)**: `check` 2회(repo·workspace 스코프). 앵커 **32**, `pending` **29**, `unmapped` **0**, `errors` **0**.
- **부작용 0 실증**: kompound `git log --oneline -1` = `9570ce7` 호출 전후 동일 / `raw/` **228개 불변** / 위키 3파일 md5 **완전 동일** / 새 dirty 없음(`M wiki/log.md`는 호출 전부터 존재).
- **범위 밖 3항목 비침범 확인**: 주제 위키 합성 코드 없음 / `task`·`tasks` 세그먼트 제외 / 모든 쓰기가 `kompound_repo` 하위로만(home repo 역방향 수정 없음).
- 정적 분석 통과, 전체 스위트 **1065 passed / 0 failed**(기존 533 + 신규 532).

### 알려진 한계 (수용, result 문서에 기록)

- **T2 게이트 프리필터의 오탐 계열** — `*rm\ -f*`/`*rm\ -r*` 패턴이 `confirm -f`(`...i`**`rm -f`**)·`charm -r`(`cha`**`rm -r`**) 같은 문자열도 잡는다(리뷰어 직접 계산 확인. 단 `npm -f`/`npm -r`은 "npm"에 `r`이 없어 미매칭). **`nocasematch`가 만든 것이 아니라 arch §5.2.2 원본 패턴에 이미 있던 성질**이고 it.2는 대문자 축으로 대칭 확장만 했다.
  - 더 좁은 대안(`-[rRfF]*` 브래킷)은 오히려 **`rm file.txt`·`rm -v report.txt`처럼 파일명에 r/f가 든 무관한 rm까지 과다 매칭**해 기각됐다(스크립트 주석 L52-54 + `LEARNING.md` 2026-08-04에 근거 기록).
  - 코어가 최종 판정하므로 **안전성 문제는 없고**, 실사용 빈도가 낮아 [P2] 성능 관찰 수준이다. **수용.**
- **T2 게이트 서브프로세스에 명시적 `timeout` 래핑 없음** — 코어가 무한 대기하면 이론상 훅이 멈춘다. 다만 락이 `O_CREAT|O_EXCL`(non-blocking, `git_state.py:534`)이고 내부 git 호출에 `_GIT_TIMEOUT_SECONDS`(`git_state.py:104`)가 이미 걸려 있어 실질 위험이 낮다. arch도 이 래핑을 요구하지 않는다. **수용(관찰).**

- **`log.md`의 카탈로그 커밋 sha 자리에 `"HEAD"` 리터럴** — 로그 줄이 자신을 포함하는 커밋(log.md)의 sha를 커밋 전에 알 수 없는 **자기 참조 순환**. 대안 3개가 모두 다른 규약과 충돌한다: amend는 (ii) 실패 롤백 복잡도↑ / 다음 실행이 sha를 채우면 `append_log`의 **append-only 규약 위반** / 커밋 메시지에만 기록하면 log.md 자체의 정보 완결성↓(§6.3.0이 log.md 단독 식별 가능성을 요구).
  - **수용 근거**: 정보 손실은 아니다 — `git log --grep 'snapshot(catalog):'`로 detail 문자열을 대조하면 역추적 가능하고, 해당 커밋 메시지 자체가 유일 식별자다.
  - **잔여 비용**: `log.md`만 단독 열람하는 사람은 실제 sha를 알 수 없다. compliance·리뷰 양쪽이 수용 판정하면서 **result 문서에 명시**하도록 권고했다(명시하지 않으면 다음 사이클에서 재논쟁된다).

- **런타임 상태 파일의 lost update** — `<project>/.claude/state/kompound-snapshot.json`은 `atomic_write`(tempfile + move)로 torn write만 막고 **파일 락이 없다**. 두 Stop 훅이 겹치면 `blocks` 증가분이 유실되어 실제 상한이 "정확히 3"이 아니라 "3 이상"으로 느슨해질 수 있다.
  - **유계다**: (a) `pending == 0`이 되면 즉시 `DONE`으로 해소 (b) 서명이 바뀌면 항상 재무장 (c) 무한 루프가 아니라 예산 상한이 느슨해지는 정도의 저하.
  - arch §5.3의 락은 **kompound repo 전용**이고 이 파일에 대한 락 요구는 arch에 없다. T-7 리뷰가 P1 기준(데이터 손실·크래시·보안·사용자에게 보이는 오동작) 미충족으로 판정했다. **수용.**

### arch 문서 수정 항목 (result 문서에 반영 — 코드 결함 아님)

- **A-doc-3 — arch §5.2.2의 프리필터 패턴이 코어 인식 집합과 불일치한다(실질 결함을 유발했다).** arch가 프리필터 `case`를 `*worktree*remove*|*rm\ -r*|*rm\ -f*|*--recursive*`로 명시했는데, bash `case`는 기본 대소문자 구분이라 **소문자만 매칭**한다. 반면 같은 절의 코어 패턴 B는 재귀 플래그 6종(`-r`/`-R`/`-rf`/`-fr`/`-Rf`/`--recursive`)을 인식하도록 규정한다.
  - **결과**: `rm -Rf <worktree>`(경계표가 "개입"으로 명시한 시나리오의 대문자 변형)가 프리필터에서 조용히 통과해 코어가 기동조차 안 됨 → **문서 영구 소실 경로**. 승인된 미탐 목록에 속하지 않는다.
  - **소재**: 구현자 잘못이 아니다 — task 문서가 arch 패턴을 그대로 인용해 지시했고 구현자는 정확히 따랐다. **arch가 프리필터↔코어 패턴 정합성을 자체 검증하지 않은 것**이 근원.
  - **조치**: T-13 it.2에서 프리필터를 코어 인식 집합과 일치하도록 수정. **arch §5.2.2에 "프리필터 패턴은 코어 인식 집합과 정합해야 하며 대소문자를 포괄한다"를 명시**하도록 result 문서에 올린다. compliance가 `LEARNING.md`에도 기록했다.

- **A-doc-1 — arch §5.1.3 결정표의 순서가 같은 절의 원칙과 충돌한다.** 표(L220-229)를 문언대로 "위에서부터 배타 평가"하면 `pending == 0`(DONE) 행이 `CATALOG_PENDING` 행보다 먼저 걸린다. 그런데 같은 절 L247과 §10.4-11은 "**`CATALOG_PENDING`을 `DONE`으로 덮으면 drift가 완전히 보이지 않게 된다**"며 그것을 명시 금지한다. raw 성공으로 `pending`이 자연히 0이 되는 순간 표 순서를 따르면 침묵 덮임이 발생 → arch가 스스로 금지한 결과.
  - **T-7 구현은 `CATALOG_PENDING` 검사를 `pending==0`보다도 앞에 배치**해 상위 원칙 쪽으로 해소했고, compliance가 "arch 의도를 더 정확히 구현한 것"으로 판정했다(회귀 테스트 2건으로 고정: `test_catalog_pending_passthrough_before_pending_zero_check`, `test_catalog_pending_checked_before_condition_four`).
  - → **arch §5.1.3 결정표에 "`CATALOG_PENDING` 검사가 `pending==0` 판정보다 선행한다"를 명시**하도록 result 문서/arch 후속 수정에 올린다. 문서만 고치면 되고 코드 변경은 없다.

- **A-doc-2 — arch §5.4.4의 정렬 키 `("worktrees" in x, len(x))`는 부분 문자열 검사다.** `my-worktrees-backup/` 같은 경로를 worktree로 오판한다. `scan.py`의 `_has_worktrees_segment`(세그먼트 인식)와 같은 코드베이스에 두 패턴이 공존한다.
  - **차단하지 않고 코드도 그대로 둔다**: (1) arch가 참고 구현 그대로 이 패턴을 명시했고 compliance가 arch 일치로 통과시켰다 — 지금 바꾸면 코드↔arch가 어긋나 다음 compliance가 역으로 지적한다. (2) `dedup()`은 `(kind, md5)`로 먼저 그룹핑하므로 정렬 대상은 **이미 바이트 동일**하다. 오판해도 raw에 쓰일 바이트는 불변이고 흔들리는 것은 로그·registry에 남는 provenance 경로뿐 — 데이터 손실 경로가 아니다.
  - → **arch §5.4.4에 "세그먼트 인식 권장, 단 그룹 내 내용 동일 불변식 때문에 데이터 영향 없음"을 주석으로 명시**하도록 result 문서에 올린다.

### T-8 확정 계약 (`registry.py`/`wiki_log.py` — **T-10 필독**)

```python
update_registry(registry_text, new_docs, *, prefix_map, totals=None) -> dict
#  성공 {"ok":True,"text","rows_added","cells_updated","columns_added":[(heading,"기타"),...]}
#  실패 {"ok":False,"reason":"catalog_unparsed","detail"}  (예외 없음)
#  new_docs 원소: {"repo_dir","project","feature","kind","raw_name","worktree"}
update_index(index_text, *, hook_line, recent_change_line) -> dict
append_log(log_text, *, line) -> dict
build_snapshot_log_line(date, total_raw, raw_commits, catalog_commit, retries) -> str
```

**arch에 없어 T-8이 직접 결정한 것 — T-10이 이대로 배선해야 한다:**
1. ~~**입력은 "신규(new) 문서만"**~~ → **폐기됨. D-impl-1로 재정의됨(위 §"설계 공백 D-impl-1" 참조).**
   - **올바른 계약**: `new_docs` = **"카탈로그 링크가 아직 없는 문서 전체"**. T-10은 **F6 분류(`new`/`updated`/`unchanged`)를 재사용하지 마라** — `verify.snapshot_population(raw_dir, prefixes) - verify.snapshot_registry_links(registry_text, prefixes)` 차집합으로 도출한다.
   - 구 계약("F6상 new만 전달")을 따르면 **CATALOG_PENDING 재시도 경로에서 registry 링크가 영구 누락**된다(1차 new→raw커밋→카탈로그실패 → 2차 F6이 `unchanged`로 재분류 → 다시는 `new_docs`에 못 들어감).
   - **T-10 추가 작업**: `snapshot_population`/`snapshot_registry_links`는 **`Set[str]`(파일명)만** 반환한다(`verify.py:158,194`). T-10이 그 파일명 집합을 `update_registry`가 요구하는 `{"repo_dir","project","feature","kind","raw_name","worktree"}` 엔트리로 **역파싱**해야 한다. (T-8 compliance 재검사 지적 — T-10 리뷰 필수 확인 항목)
2. **`totals`는 opt-in** — 생략하면 카운트 문장 2종을 건드리지 않는다. **총계 계산(§6.3.1 `snapshot_set_rule` 기반 raw/feature 집계)은 T-10 또는 T-9 `verify.py`가 해서 전달**해야 한다. 전달 안 하면 카운트가 갱신되지 않는다.
3. **`기타` 열은 ui/api/context 3종의 통합 열 하나뿐**이다(실측 registry 확인). "없는 kind 열 추가"가 실제로 추가하는 열은 항상 `기타`.
4. **`wiki_log.py`는 index/log 문장 내용을 작성하지 않는다** — `hook_line`/`recent_change_line`은 **호출자(T-10)가 완성된 문자열로 조립해 전달**한다(텍스트 스플라이스 위치만 이 모듈 책임). 단 `log.md`의 raw/카탈로그 두 시점 표기는 arch §6.3.0이 리터럴로 확정한 템플릿이라 `build_snapshot_log_line()`이 직접 조립한다.
5. **행 삽입 위치는 같은 프로젝트 행 그룹의 마지막 뒤**(표 전체의 마지막이 아님) — `moon-harness` 실측(3행이 그룹으로 뭉쳐 있음)과 일치.

### T-10 확정 계약 (`apply.py` — T-11이 CLI에서 호출)

```python
apply(kompound_repo, canonical_records, *, prefix_map, scan_root=None, project_root=None) -> dict
# {"busy","precondition_failed","precondition","unmapped","dirty","raw_name_conflicts",
#  "raw_stage":{...arch §6.2...}, "catalog_stage":{...arch §6.2...}}
```
- `project_root`는 arch에 없던 **선택 인자** — 주면 `runtime_state.record_apply_outcome()` 호출, 생략하면 상태 기록 스킵(단위 테스트용).
- 이월 5건 처리 위치: **D-impl-1** `_run_catalog_stage`(차집합 `missing` → `should_run_gates({"new": missing, "updated": []})`) / **C-4·C-6** `_prepare_raw_writes`(raw_name 그룹핑 → `(-mtime, path)` 정렬로 최신 채택 + `raw_name_conflicts` 항상 보고) / **C-7** `_compute_totals`(카탈로그 시도마다 계산해 `totals=` 전달) / **`precondition_failed`** `_apply_impl`(필드 그대로 사용, 재조립 안 함).
- `raw_name` 충돌은 **새 verdict를 만들지 않고** 승자를 정상 write·커밋해 `snapshotted`로 수렴 + `raw_name_conflicts` 필드로 가시화(근거: spec F5가 "mtime 최신본 채택"을 정상 동작으로 명시하므로 실패가 아니다).

**T-10이 arch 없이 직접 결정한 것 (검증 대상)**
1. `build_snapshot_log_line`의 `catalog_commit` 자리에 **`"HEAD"` 리터럴** — 로그 줄이 자신을 포함하는 커밋(log.md)의 sha를 커밋 전에 알 수 없는 순환을 amend 없이 회피.
2. 카탈로그 재시도 이력(`raw_commits`/`retries`)을 새 영속 상태 없이 **`git log`에서 마지막 `snapshot(catalog):` 이후의 `snapshot(raw):` 커밋들을 조회**해 도출. `retries`는 근사치이며 **차단/판정 로직에는 미사용**(log 문구 조립 전용).
3. `hook_line`/`recent_change_line`을 이 모듈이 기계적 사실(날짜·건수·프로젝트·총계)만으로 조립(T-8이 호출자 책임으로 명시한 부분).
4. `_decompose_raw_name()`이 `verify.matches_snapshot_rule`과 **동일 판정식을 재구현**(호출이 아니라 재구현). rich 경로는 알려진 `project`/`kind`로 `_feature_from_basename` 직접 호출, 폴백 경로만 `_decompose_raw_name` 사용(다중 프리픽스 매칭 시 최장 우선).

### T-9 확정 계약 (`verify.py` — T-10이 (ii) 단계에서 호출)

- `effective_prefixes(prefix_map)` — `.values()`에서 `None` 제거·정렬·유일화
- `matches_snapshot_rule(filename, prefixes)` — 순수 판정. kind 접미사 매칭 후 remainder가 `<prefix>-`로 시작하고 feature가 비어있지 않을 때만 인정
- `snapshot_set_rule(prefix_map)` → `{"prefixes","kinds","matches"}` — arch §6.3.1 캡슐화. **게이트가 이 dict의 `matches`를 위임 사용**해 판정 로직 이원화를 방지
- `snapshot_population(raw_dir, prefixes)` / `extract_registry_raw_links(text)` / `snapshot_registry_links(text, prefixes)`
- `check_link_integrity` / `check_bidirectional_count` / `check_flat_structure` → 각 `{"gate","ok","detail"}`
- `should_run_gates(raw_stage)` — 스킵 판단 분리(malformed면 fail-safe `True`)
- `run_gates(kompound_repo, prefix_map)` → 3개 리스트(arch §3.2 원 계약)
- `build_verify_report(...)` → `{"prefixes":[...], "gates":[...]}` — 프리픽스 목록 노출

> **실제 kompound 실측(읽기만, 2026-07-30)**: naive kind 접미사 **122** → `snapshot_set_rule` **117**(초과 5건 정확 제외) / registry 스냅샷 링크 **117** / 양방향 차집합 **0** / 3게이트 전부 `ok=True`. **C-1이 프로덕션 데이터로 해소 확인됨.**

### 이월 실행 항목 (T-2 compliance 관찰사항 — 담당 태스크가 처리한다)

| # | 내용 | 담당 |
|---|------|------|
| C-1 | 정적 검사의 허용 non-stdlib 루트가 `{"hooks"}`로 **arch §4보다 느슨하다**(§4는 `hooks.lib.self_improve.state_io` 단방향만 허용). → **T-2 리뷰에서 [P1]로 격상**(주석은 좁게 주장하는데 로직은 `hooks.*` 전체를 통과시켜, 후속 10개 태스크의 유일한 자동 아키텍처 가드가 무력). **T-3으로 이월하지 않고 T-2 iteration 2에서 해소**한다. | ~~T-3~~ → **T-2 (it.2)** |
| C-5 | ~~해소(T-7 `19a8f8e`)~~ — T-7이 `runtime_state.STATUSES`를 `report.RUNTIME_STATUSES`와 **tuple-equality 테스트로 고정**했다. 이름 불일치는 이제 테스트가 잡는다. T-11은 대조 불필요, 다만 `report.py`가 `runtime_state` 상수를 import하도록 교체할지는 선택. (원 내용: **`report.RUNTIME_STATUSES`가 상태 6종 문자열을 하드코딩**하고 있다(T-6 구현 시점에 `runtime_state.py`가 없던 순서 제약). docstring·주석에 "단일 진실은 `runtime_state.py`, 여기는 스키마 참조용"이라 명시돼 있다. → **T-11 착수 전에 T-7의 실제 상수 이름과 어긋나지 않는지 대조**하고, `runtime_state`의 상수를 import하도록 교체할지 판단한다. 어긋나면 통합에서 조용히 깨진다. | **T-11** |
| C-7 | **`totals`를 반드시 계산해 전달해야 한다.** `update_registry(totals=None)`이면 카운트 문장 2종이 **조용히 미갱신**된다(T-8 compliance 항목 21 — arch §3.2/§6.3.1이 총계 계산을 registry 모듈 밖으로 위임한 것 자체는 정당). 실수로 누락하면 F7의 카운트 요구가 매 실행 조용히 미이행된다. → **T-10은 실제 apply 경로에서 항상 `totals`를 계산해 전달**하고, **T-10 리뷰가 이 불변식을 명시 확인**한다. | **T-10** |
| C-6 | **`raw_name` 충돌 검출은 T-10 책임이다.** 서로 다른 원본이 같은 `raw_name`으로 수렴할 수 있다(예: `2026-01-01-widget-spec.md`와 `widget-spec.md`가 같은 kind·project → 둘 다 feature `widget`). 내용이 다르면 dedup이 `(kind, md5)` 그룹핑으로 막지 못해 각각 naming까지 도달한다. `name_document`는 레코드 1건당 결정적으로 `raw_name` 하나를 반환하고 입력과 1:1 대응이 보장되므로, **T-10이 `records`와 출력을 zip해 `raw_name → [record]` 맵을 만들면 충돌을 완전히 검출할 수 있다.** → **T-10 구현·리뷰 시 이 맵을 실제로 만들어 충돌을 처리하는지 반드시 확인**(안 하면 한쪽이 다른 쪽을 조용히 덮어쓴다). | **T-10** |
| C-4 | **F5 "내용 상이 시 mtime 최신본 채택"의 실제 선택 로직은 T-4 스코프 밖이다.** `dedup.py`는 다른 `(kind, md5)` 그룹을 별개 canonical 레코드 2건으로 반환하고 원본 dict(=`mtime` 포함)를 보존하는 데까지만 한다. **두 문서가 동일 `raw_name`으로 수렴할 때 어느 쪽을 쓸지 결정하는 것은 `apply.py`의 책임**이다. → **T-10 구현·검증 시 mtime 기준 선택이 실제로 구현됐는지 반드시 확인**(미구현이면 F5 Acceptance 미충족). | **T-10** |
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
