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
- 상태: EXECUTING
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
- 현재 Wave: 0 (착수 대기)
- 완료 Wave: 없음

---

## 태스크 상태

| ID | Wave | 구현자 | Status | Iteration | Agent | 비고 |
|----|------|--------|--------|-----------|-------|------|
| T-1 | 0 | sdd-test-automator (refactor) | pending | 0 | - | F17 회귀 안전망. **Wave 5 게이트 조건**(§"Wave 0 게이트" 참조) |
| T-2 | 0 | sdd-python-engineer | pending | 0 | - | 패키지 뼈대 + `fake_kompound_env` fixture |
| T-3 | 1 | sdd-python-engineer | pending | 0 | - | `config.py` (F16) |
| T-4 | 1 | sdd-python-engineer | pending | 0 | - | `scan.py`/`naming.py`/`dedup.py` (F3/F4/F5/F12) |
| T-5 | 1 | sdd-python-engineer | pending | 0 | - | `git_state.py` (F9) |
| T-6 | 1 | sdd-python-engineer | pending | 0 | - | `wt_target.py`/`report.py` (F2 파싱, F11) |
| T-7 | 1 | sdd-python-engineer | pending | 0 | - | `runtime_state.py` (F1 상태 6종) |
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
