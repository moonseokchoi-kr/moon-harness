# kompound-snapshot-hook — 아키텍처 설계

- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` (F1~F17 + D1~D4)
- 설계 SSOT(상위): `/Users/moon/workspace/marvelous_kompound/raw/sdd-kompound-snapshot-hook.md`
- 모드: SIMPLE (UI/API 산출물 없음)
- 티어: **하네스 티어** — `hooks/enforcement/` 신규 게이트 + `stop-pipeline.py` 수정 포함 → **protected set, 사람 승인 필수**(F15, 아래 §10.1)

---

## 1. 아키텍처 요약

세 개의 레이어로 나눈다. **결정은 전부 Python 결정적 코어에, 트리거는 얇은 어댑터에, 판단은 어디에도 두지 않는다.**

```
 [트리거 어댑터]                      [결정적 코어]                    [외부 상태]
 ─────────────────                   ───────────────────              ────────────
 T1  stop-pipeline.py                hooks/lib/kompound_snapshot/     kompound repo
     (Stop 훅, 기존 파일)      ──▶     config  scan  naming            raw/*.md
     STATE=COMPLETED 감지 →            dedup   apply registry          wiki/sdd-spec-registry.md
     directive 주입 + 전진 보류        wiki_log verify git_state        wiki/index.md
                                      wt_target report runtime_state   wiki/log.md
 T2  kompound-snapshot-gate.sh  ──▶   cli(check | apply | gate)
     (PreToolUse:Bash, 신규)                    │                     .claude/state/
     명령 프리필터만 bash               ─────────┘                      kompound-snapshot.json
                                                                       (런타임 상태)
 수동  python3 -m hooks.lib.kompound_snapshot ...
```

핵심 원칙 4개:

1. **단일 판정 구현.** 스캔·네이밍·dedup·멱등·검증은 코어에만 존재한다. T1은 코어를 in-process import, T2는 서브프로세스로 호출한다(D4). bash에 규칙을 복제하지 않는다 — 두 트리거의 판정이 갈리는 것이 최악의 실패다.
2. **자동 편입은 강제, 자동 판단은 금지.** 코어는 문서를 verbatim 복사하고 카탈로그의 기계적 필드만 고친다. 주제 위키 합성·문장 작성은 하지 않는다(F7 범위 고정).
3. **트리거 어댑터는 사실만 읽는다.** T1은 `ORCHESTRATOR_STATE.md`의 상태와 런타임 상태 파일만 본다. T2는 Bash 명령 문자열만 본다. 둘 다 "무엇을 박제할지"는 모른다.
4. **비활성화 가능해야 한다.** kompound 경로가 해석되지 않는 사용자에게 이 기능은 존재하지 않는 것처럼 동작한다(F16). 범용 플러그인의 제약이다.

---

## 2. 가정 · 제약 · 성능 목표

### 2.1 가정 (전부 확정 — 2026-07-29)

| # | 가정 | 근거 |
|---|------|------|
| A1 | 언어/런타임 = Python 3 stdlib-only + bash. 신규 의존성 0 | CLAUDE.md 결정↔판단 분리, `hooks/lib/self_improve/` 선례 |
| A2 | 테스트 프레임워크 = pytest (기존 스위트 533 passed) + `unittest.mock`. hypothesis 등 신규 도입 없음 | `tests/` 기존 관례. **기술 판단으로 확정**(§9.3, §10.4-1) |
| A3 | 코어는 `git` 서브프로세스를 호출한다(네트워크 아님). `fetch`/`pull`/`push`는 하지 않는다 | F13 "네트워크 무호출" vs F9 divergence 판정의 양립 → §6.4 |
| A4 | 훅은 kompound에 **로컬 커밋까지**(A-5 이후 raw·카탈로그 최대 2개) 하고 push는 하지 않는다 | spec에 push 요구 없음. **사용자 승인 2026-07-29**(§10.4-2) |
| A5 | `jq`는 게이트에서 사용 가능(기존 5개 게이트 전제) | `worktree-add-gate.sh` |
| A6 | `python3`은 hook 실행 환경에 존재. 없으면 fail-safe 통과 | `stop-pipeline.sh` 선례 |

### 2.2 플랫폼 제약

- macOS/Linux 우선, Windows(Git-bash)에서 깨지지 않아야 한다 → 경로는 `pathlib` + POSIX 정규화, `PYTHONUTF8=1` 유지(`pipeline-utils.sh`·`stop-pipeline.sh` 선례). `_winify_path` 계열 보정은 stop-pipeline.py의 기존 함수를 재사용한다.
- 훅은 대화형이 아니다. 사용자 입력을 기다리는 코드 경로는 금지.
- 동시성: PreToolUse 게이트와 Stop 훅이 동시에 코어를 띄울 수 있다 → kompound 쓰기는 배타 락 필요(§5.3).

### 2.3 성능 목표 (실측 기반 상한)

| 경로 | 목표 | 근거 / 위험 |
|---|---|---|
| T2 프리필터(bash, 무관 명령) | **< 5ms**, python 미기동 | PreToolUse는 모든 Bash 명령에 붙는다. 여기서 python을 띄우면 전체 세션이 느려진다 |
| `check` — worktree/repo 스코프 | < 300ms | `gate_perf_warn` 기준 100ms를 초과하나, 대상 명령이 `git worktree remove`/`rm -rf`뿐이라 허용. 초과 시 경고만 |
| `check` — workspace 스코프 | < 3s | 수동/백필 전용. T1·T2는 이 스코프를 쓰지 않는다 |
| T1 Stop 훅 게이트(무장 안 됨) | < 20ms | 런타임 상태 파일 1회 read + STATE 파일 1회 read + mtime stat 1회로 끝난다. 코어 import도 하지 않는다(지연 import) |
| T1 Stop 훅 게이트(**무장됨**) | **< 300ms** | 무장 시에만 코어를 import하고 in-process `check`(repo/worktree 스코프)를 1회 돈다 — `check` 목표와 동일한 상한. 사이클당 최대 3~4회(블록 예산 3 + `DONE` 확정 1)만 발생하므로 세션 전체 비용은 무시 가능 |

**스캔 비용을 상한하는 설계 결정 — 앵커 탐색 깊이 제한.** 스캔 루트(`/Users/moon/workspace`)에는 Marvelous급 C++ 레포가 여럿 있어 전체 `os.walk`는 수 초가 걸린다. 그래서 2단 스캔으로 나눈다:

1. **앵커 탐색** — 루트에서 깊이 ≤ `max_anchor_depth`(기본 5)까지만 순회해 `docs/sdd` · `Docs/sdd` 디렉토리를 찾는다. 실측 케이스는 전부 깊이 4 이내다(`workspace/<repo>/worktrees/<wt>/docs/sdd`, `workspace/<repo>/<sub>/docs/sdd`).
2. **앵커 하위 전수 순회** — 앵커 아래는 깊이 제한 없이 전부 순회한다(`SKIP_DIRS` 적용).

깊이 제한은 설정값이며 리포트에 `anchors=N depth_limit=D`를 항상 출력한다 → "조용한 미탐"이 되지 않는다(F11 정신).

---

## 3. 모듈 / 라이브러리 분해

### 3.1 디렉토리 경계 (모듈 단위 — 파일명은 확정 항목만 명시)

```
hooks/
  lib/
    self_improve/                 (기존, 변경 없음 — state_io만 재사용)
    kompound_snapshot/            ★ 신규 결정적 코어 패키지 (self_improve와 형제)
      __init__.py                 공개 API 재노출 (self_improve/__init__.py 관례)
      __main__.py                 python3 -m hooks.lib.kompound_snapshot 엔트리
      cli.py                      ★ 서브커맨드 파싱 + main(argv) (evals/run_eval.py 관례)
      config.py                   F16 설정 해석 (단일 진실 지점 resolve_config)
      scan.py                     F3 앵커 탐색 · 포함/제외 · md5 수집
      naming.py                   F4 네이밍 + F12 미등록 판정
      dedup.py                    F5 md5 그룹핑 · canonical 선택
      apply.py                    F6 멱등 적용 + 트랜잭션 저널/롤백
      registry.py                 F7 sdd-spec-registry.md 표/카운트 외과적 갱신
      wiki_log.py                 F7·F10 index.md prepend · log.md append
      verify.py                   F8 검증 게이트 3종
      git_state.py                F9 dirty/divergence 판정 · 커밋 · 배타 락
      wt_target.py                F2 Bash 명령 → 워크트리 경로 파싱
      report.py                   F11 verdict/exit code · human/JSON 리포트
      runtime_state.py            T1 멱등·무장·안내 1회 상태 (.claude/state/)
  enforcement/
    stop-pipeline.py              ◆ 기존 파일 수정 (F1, protected)
    kompound-snapshot-gate.sh     ★ 신규 T2 게이트 (F2·F14, protected)
    lib/                          (기존 constants.sh/logging.sh 재사용, 무변경)
  hooks.json                      ◆ PreToolUse:Bash 배열에 1항목 추가 (F14, protected)
skills/
  sdd-orchestrator/SKILL.md       ◆ Step 4-2와 4-3 사이에 박제 스텝 문서화 (F1)
tests/
  (신규 테스트 파일군 — §9)
```

`★` 신규 · `◆` 기존 파일 수정. 수정 대상 3개(`stop-pipeline.py`, `hooks.json`, 신규 게이트 스크립트)는 전부 protected set → §10.1.

### 3.2 모듈 책임과 계약 (요약)

| 모듈 | 입력 | 출력 | 부작용 |
|---|---|---|---|
| `config` | env, 설정 파일, 프로젝트 루트 | `{"ok", "kompound_repo", "scan_root", "prefix_map", "max_anchor_depth", "state_max_age_hours", "source"}` | **없음** — 안내 출력 판정은 `runtime_state` 소유(M-18) |
| `scan` | 스코프 루트 리스트, config | `[{"kind","path","md5","mtime","repo_dir"}]`, `{"anchors","errors"}` | 없음(read-only) |
| `naming` | 문서 레코드, prefix_map | `{"raw_name"}` 또는 `{"unmapped": repo_dir}` | 없음(순수 함수). `repo_dir` 도출은 §5.4.2 |
| `dedup` | 문서 레코드 리스트 | canonical 레코드 리스트 | 없음(순수 함수) |
| `apply` | canonical 리스트, kompound_repo | **2단 결과** `{"raw_stage":{…}, "catalog_stage":{…}}`, 단계별 저널 (§6.3.0) | (i) `raw/*.md` write + 커밋 → (ii) wiki 3파일 write + 커밋 |
| `registry` | 적용 결과, registry 텍스트 | 새 registry 텍스트 또는 `{"ok": False, "reason"}` | 없음(텍스트 변환) |
| `wiki_log` | 적용 결과, index/log 텍스트 | 새 텍스트 | 없음(텍스트 변환) |
| `verify` | kompound_repo 상태 + **`snapshot_set_rule`**(§6.3.1) | `[{"gate","ok","detail"}]` × 3 | 없음(read-only) |
| `git_state` | kompound_repo | `{"dirty":[], "ahead", "behind", "upstream"}` / 커밋 결과 | git index/HEAD(커밋 시), 락 파일 |
| `wt_target` | Bash 명령 문자열 | `[worktree_path]` | 없음(순수 함수) |
| `report` | verdict + 세부 | exit code, human text, JSON | stdout/stderr write |
| `runtime_state` | 프로젝트 루트, session id | 상태 dict + **안내 1회 판정**(M-18) | `.claude/state/kompound-snapshot.json` write |

**모든 모듈은 예외를 밖으로 던지지 않는다.** 구조화된 결과 dict(`{"ok": bool, ...}`)를 반환하는 `self_improve` 관례를 그대로 따른다. 최상위 `cli.main()`이 남은 예외를 `SCAN_ERROR`로 변환한다(F13 fail-safe, F11 "조용한 0건 금지").

---

## 4. 소유권과 의존 방향

```
stop-pipeline.py ──sys.path 부트스트랩 후 지연 import──▶ kompound_snapshot.{cli,config,runtime_state}
kompound-snapshot-gate.sh ──subprocess(PYTHONPATH=plugin root)──▶ python3 -m hooks.lib.kompound_snapshot gate
kompound_snapshot.cli ──▶ config → scan → naming → dedup → apply → registry/wiki_log → verify → git_state
kompound_snapshot.* ──▶ hooks.lib.self_improve.state_io (atomic_write/load_state/now_iso/parse_iso)
```

규칙:

- **의존은 한 방향.** `self_improve`는 `kompound_snapshot`을 절대 import하지 않는다. `kompound_snapshot`이 `self_improve.state_io`만 단방향으로 재사용한다(원자적 write·ISO 시간 유틸 중복 구현 회피).
- **경로 부트스트랩은 어댑터 책임.** 코어는 자신이 어떻게 import됐는지 모른다. `sys.path`(T1) / `PYTHONPATH`(T2) 설정은 각 어댑터가 한다 — `stop-pipeline.sh`가 `PYTHONPATH`를 설정하지 않기 때문에 T1은 `stop-pipeline.py` 안에서 직접 부트스트랩해야 한다(§5.1.2). 이것을 빼먹으면 `ModuleNotFoundError`로 T1이 전부 무효화된다.
- **어댑터는 코어를 알지만 코어는 어댑터를 모른다.** 코어에 "Stop 훅"·"PreToolUse" 개념은 없다. `gate` 서브커맨드도 "명령 문자열 → verdict" 순수 변환이다.
- **파일 소유권**: `raw/*.md`와 registry/index/log 3개 파일은 코어만 쓴다. `.claude/state/kompound-snapshot.json`은 코어(`runtime_state`)만 쓴다 — stop-pipeline.py는 이 모듈을 통해서만 접근하고 직접 json을 만들지 않는다(`state_io` 규칙 계승).
- **home repo는 read-only.** 코어는 스캔 루트 하위에 절대 쓰지 않는다(단방향, spec 범위 밖 항목).

---

## 5. 제어 흐름 · 이벤트 흐름

### 5.1 F1 — T1: stop-pipeline.py 통합

#### 5.1.1 실측된 제약 3개 (설계를 결정한 사실)

| # | 사실 | 근거 | 영향 |
|---|---|---|---|
| C1 | `DIRECTIVES`의 `PHASE4_WORKTREE_CREATED`는 **터미널**(`None`)이고 `decide()` Step 5가 이 라벨에서 즉시 `{"continue": True}`를 반환한다. spec F1이 언급한 `PHASE4_ALL_TASKS_DONE`·`PHASE4_RESULT_GENERATED`·`PHASE4_MERGED`는 `skills/sdd/SKILL.md` L158-164에 **문서로만** 존재하고 stop-pipeline.py·pipeline-utils.sh 어디서도 설정되지 않는다 | stop-pipeline.py L158/L371, SKILL.md L164 | 라벨 체인 연장으로 T1을 구현하면 **라벨이 영원히 오지 않아 발화 0회**가 된다 → 라벨 체인 연장 채택 불가 |
| C2 | `decide()` Step 2 `is_stale`(2시간)과 Step 3 세션 매칭이 라벨 판정보다 먼저다. 실제 Phase 4는 수 시간~수 세션에 걸친다 | stop-pipeline.py L352-359 | Phase 4 완료 시점의 pipeline.json은 거의 확실히 stale/세션 불일치 → 기존 스텝 뒤에 넣으면 발화하지 않는다 |
| C3 | Phase 4는 `pipeline.json`이 아니라 `docs/sdd/ORCHESTRATOR_STATE.md`로 운영된다. `/sdd-orchestrator` 직접 실행 시 pipeline.json이 아예 없을 수 있다(Step 1이 `{"continue": True}` 조기 반환) | sdd-orchestrator/SKILL.md, stop-pipeline.py L348-350 | 박제 상태를 pipeline.json에 두면 사이클의 일부를 놓친다 → **별도 런타임 상태 파일 필요** |

→ **결론: 라벨 체인에 끼워 넣지 않는다. `decide()` 최상단(Step 0 직후)에 pipeline.json과 독립적인 완료 게이트를 신설한다.** 이 위치 선택은 부수 효과로 F17 회귀 안전망을 지킨다 — 게이트가 비활성일 때 기존 Step 1~9의 동작이 입력별로 완전히 동일하기 때문이다.

#### 5.1.2 확정 사항

| 항목 | 확정값 |
|---|---|
| DIRECTIVES 신규 키(의사 라벨) | `PHASE4_KOMPOUND_SNAPSHOT_PENDING` |
| 상태 필드 위치 | `<project_root>/.claude/state/kompound-snapshot.json` (pipeline.json 아님 — C3) |
| 상태 값 | `PENDING` \| **`CATALOG_PENDING`** \| `DONE` \| `SKIPPED_UNCONFIGURED` \| `FAILED` \| `GIVEN_UP` |
| `CATALOG_PENDING` 의미 | (i) raw 복사·커밋 성공 + (ii) 카탈로그 실패. **T1 판정에서 `DONE`과 동일하게 통과 처리**(재차 block 없음, 블록 예산 미소모) |
| 자체 블록 상한 | `KOMPOUND_MAX_BLOCKS = 3` — **자체 카운터 전용**, 기존 `CB_MAX_BLOCKS=20`과 상태를 공유하지 않는다(§5.1.4) |
| 블록 예산 스코프 | 세션 — 런타임 상태의 `armed_session_id`가 바뀌면 예산 초기화 |
| STATE 파서 | `- 상태: <VALUE>` 와 `status: <VALUE>` 둘 다 허용(§10.3 발견 사항) |
| STATE 신선도 상한 | `KOMPOUND_STATE_MAX_AGE_HOURS = 24` (설정 `state_max_age_hours`로 교체 가능) — **보조 조건**(§5.1.3 조건 2) |
| block 반환 조건 | **런타임 상태 write 성공 시에만**(A-1 원칙, §5.1.4) |
| 실패 사용자 노출 | 런타임 상태의 `FAILED`/`GIVEN_UP`을 **T2가 승계해 `gate_warn`으로 출력**(A-2). T1 stderr는 평시 비관측 |
| 코어 import 부트스트랩 | `sys.path.insert(0, <plugin root>)` — 아래 필수 |

**코어 in-process import 부트스트랩 (필수)**

`hooks/enforcement/stop-pipeline.sh`는 `exec python3 "$SCRIPT_DIR/stop-pipeline.py"`만 하고 `PYTHONPATH`를 설정하지 않는다(`PYTHONUTF8=1`만 export). 따라서 `sys.path[0]`은 `<plugin>/hooks/enforcement`이고, 부트스트랩 없이는 `import hooks.lib.kompound_snapshot`이 **`ModuleNotFoundError`** 로 실패한다. stop-pipeline.py 안에서 다음을 수행한다:

1. plugin root = `CLAUDE_PLUGIN_ROOT`(설정돼 있으면, `_winify_path` 통과) → 없으면 `Path(__file__).resolve().parents[2]`.
2. `sys.path`에 없으면 `sys.path.insert(0, str(plugin_root))`.
3. import는 **완료 게이트 함수 내부에서 지연 수행**한다(모듈 최상위 import 금지). 이유: ① 게이트가 무장되지 않은 대다수 호출에서 import 비용 0 ② import 실패가 모듈 로드 자체를 깨뜨려 기존 파이프라인 전체를 무력화하는 일을 막는다 ③ F17 안전망이 `importlib`으로 이 모듈을 적재할 때 부작용이 늘지 않는다(§9.2의 "부작용 0" 전제 유지).
4. 부트스트랩(1~2)은 모듈 최상위에서 수행해도 무해하나, **`sys.path` 변경 외의 부작용을 만들지 않아야 한다**. F17 안전망에 "부트스트랩 후에도 기존 9개 Step 동작이 입력별로 불변"임을 고정하는 케이스를 둔다(§9.2).

`PHASE4_KOMPOUND_SNAPSHOT_PENDING`은 선형 라벨 체인의 원소가 **아니다** — 완료 게이트가 directive 문자열을 조회하는 키다. `decide()`는 `current_label`로만 `DIRECTIVES`를 조회하므로 키 1개 추가가 기존 16개 라벨의 동작을 바꾸지 않는다.

**directive 문구의 성격** — "무엇을 실행하라"의 명령형 1개 + 실패 시 행동 1개로 제한한다:
1. kompound 박제를 지금 실행하라(절대경로가 박힌 실행 커맨드 제시).
2. 성공/실패 결과를 사용자에게 보고하라. 실패해도 사이클을 되돌리지 말고 사용자 판단을 요청하라.
3. self-improve(Step 5)보다 **먼저** 끝내라.

> 📌 directive 문자열 치환은 `str.format` 금지. 기존 directive 값들이 `{YYYY-MM-DD}`·`{feature}` 같은 리터럴 중괄호를 포함하므로 format이 `KeyError`로 죽는다. 리터럴 토큰(`@@CLI@@`, `@@SCOPE@@`)과 `str.replace`를 쓴다.

#### 5.1.3 "박제 미완이면 전진 금지"의 판정

**네 조건의 AND**로 판정한다. 파일 존재만으로는 판정할 수 없다는 것이 C1/C2가 알려준 교훈이다.

1. **무장(arming) — STATE 서명 변화.** `ORCHESTRATOR_STATE.md`의 (feature, 상태, result 문서 경로) 서명을 런타임 상태에 baseline으로 기록한다. **서명이 baseline과 달라졌을 때만** 발화한다. 첫 관측은 baseline 등록이고 발화하지 않는다.
   - 이유: 머지된 과거 사이클의 `ORCHESTRATOR_STATE.md`(상태=COMPLETED)가 main에 남아 있고, worktree 체크아웃으로 mtime이 오늘로 갱신된다 → mtime 신선도만으로는 **진행 중인 사이클의 Phase 2에서 오발화**한다. 실제로 `.harness/LEARNING.md` 2026-07-01 엔트리(file-ownership 오탐)가 같은 함정을 기록했다.
   - 알려진 미탐: 세션의 **첫** Stop 훅이 이미 COMPLETED를 본 경우 baseline=COMPLETED가 되어 T1이 발화하지 않는다. Stop 훅은 매 턴 발화하므로 현실적 확률은 낮고, 남는 위험은 T2가 받는다.
2. **STATE 신선도 — `ORCHESTRATOR_STATE.md`의 mtime이 `state_max_age_hours`(기본 24h) 이내.**
   - **정확한 근거(A-4 정정)**: mtime 상한은 **클론/체크아웃 케이스를 막지 못한다** — 체크아웃이 mtime을 "방금"으로 갱신하므로 새 클론·새 워크트리의 오래된 COMPLETED STATE도 이 조건을 통과한다. 그 케이스의 실제 방어는 ① `pending == 0` 즉시 통과(과거 사이클 문서는 이미 박제돼 있다) ② 블록 예산 3회 상한이다.
   - 조건 2가 커버하는 범위는 **"오래 방치된 STATE의 내용만 바뀐" 좁은 케이스**다(예: 로컬에서 오래 묵은 repo의 STATE를 사람이 편집). 비용이 stat 1회로 0에 가깝고 일부 오발화를 실제로 줄이므로 **보조 조건으로 유지**한다. 주 방어는 조건 1(서명 변화) + 조건 4(`pending`)다.
   - mtime은 **Step 4-2가 COMPLETED를 쓴 시각**이다. Stop 훅이 매 턴 발화하므로 4-2를 수행한 턴이 끝나는 즉시 무장 판정이 이뤄진다 — **사이클 전체가 며칠 걸려도 24h 조건과 무관**하다.
3. **상태 == COMPLETED** (D1 = Step 4-2 직후).
4. **코어 `check`(부작용 없음) 결과가 `pending ≥ 1`** — 스코프는 프로젝트 루트 + (pipeline.json/STATE에 기록된) 워크트리 경로. 종료 코드가 아니라 in-process 결과 dict를 읽는다.
   - **`pending`은 "프리픽스가 매핑된 미박제 문서"만 센다.** F12 미등록 문서는 `unmapped` 별도 카운터로 분리되며 `pending`에 들어가지 않는다(§5.4.3, J-11). 근거: 미등록 문서는 directive를 따라도 박제될 수 없으므로 `pending`에 넣으면 **해소 불가능한 지시로 블록 예산 3회를 태우고** `GIVEN_UP`으로 끝난다. T1 무장은 `pending`만 본다. 미등록 문서에 대한 조치는 T2(삭제 직전 차단)와 `check`/`apply`의 경고 리스트가 담당한다.

**블록 예산의 세션 격리** — 런타임 상태에 `armed_session_id`(무장 시점의 `CLAUDE_SESSION_ID`)를 기록하고, 현재 세션이 다르면 `blocks`를 0으로 초기화한다. 이유: 예산이 전역이면 이전 세션에서 이미 소진된 카운트 때문에 **정당한 다음 세션이 3회를 온전히 받지 못한다**.

판정 결과별 동작:

| 판정 | 동작 | 상태 기록 |
|---|---|---|
| 무장 안 됨 / STATE 오래됨 / 상태≠COMPLETED | 아무것도 하지 않고 기존 Step 1로 진행 | baseline만 갱신 |
| config 미해석 (F16) | `{"continue": True}` — 전진 허용 | `SKIPPED_UNCONFIGURED` + 안내 1회 |
| `pending == 0` | `{"continue": True}` | `DONE` (재진입 시 무동작 — F1 멱등) |
| **직전 상태가 `CATALOG_PENDING`** (raw는 됐고 카탈로그만 남음) | `{"continue": True}` — **`DONE`과 동일하게 통과** | `CATALOG_PENDING` 유지, **`blocks` 미증가** |
| `pending ≥ 1`, blocks < 3 | `{"decision":"block","reason": directive}` | `PENDING`, `blocks += 1` |
| `pending ≥ 1`, blocks == 3 | **마지막 1회 block**에 "3회 안내했으나 미완 — T2가 워크트리 삭제 시 재차 막는다" 문구를 붙여 반환한 뒤 | `GIVEN_UP` (다음 Stop부터 통과) |
| **런타임 상태 write 실패** (읽기 전용 체크아웃 · `.claude/` 권한 · `CLAUDE_PROJECT_DIR` 미설정으로 cwd 쓰기 불가) | **block하지 않고 `{"continue": True}` + 경고** | 기록 불가(당연) — 다음 Stop에서 동일 판정을 재시도 |
| **코어 예외 / import 실패 / 부트스트랩 실패** | `{"continue": True}` — **통과.** 사유를 상태에 기록(가능하면)하고 stderr에 1회 경고 + T2 승계 노출 | `FAILED` (블록 예산 소모 없음) |

> 📌 마지막 두 행은 §5.2.4가 선언한 원칙과 통일한 결과다 — **"문서가 위험하다고 판정됨" → 차단 / "판정 자체를 못 했음" → 경고 후 통과.** T1에서 import 실패를 block으로 처리하면, 판정 불가 상태에서 SDD 사이클 완료를 막게 되어 F1("영구 차단 금지")과 §5.2.4 원칙 양쪽에 배치된다. T2가 삭제 직전에 다시 막으므로 소실 방어는 유지된다.

> ⚠️ **write 실패 행이 없으면 영구 블록 경로가 생긴다(A-1).** `blocks`를 기존 브레이커와 분리한 순간(§5.1.4) 런타임 상태 write가 **block의 전제 조건**이 됐다. 저장이 실패하는데 block을 반환하면 다음 Stop에서 `blocks`가 다시 0으로 읽혀 무한 block이 되고, 상태를 공유하지 않으므로 `CB_MAX_BLOCKS=20`이 구제하지 못한다 → F1 "영구 차단 금지" 위반. 그래서 **write 성공을 확인한 뒤에만 block을 반환한다**(원칙문은 §5.1.4).

**T1의 (i)/(ii) 정책 (A-5 일관성, 2026-07-29)** — T1도 T2와 같은 3축 원칙(§5.2.4)을 따른다. 위 판정표의 `pending ≥ 1` 행에서 directive를 따라 `apply`가 실행된 **뒤** 결과에 적용되는 규칙이다.

| 상황 | 상태 기록 | T1 동작 | 근거 |
|---|---|---|---|
| (i)·(ii) 모두 성공 | `DONE` | 통과 | 완료 |
| (i) raw 복사 실패 (`write_failed`) | `PENDING` | **F1의 실패 보고 경로** — 실패를 보고하고 블록 예산 내에서 재안내(사이클 완료를 영구 차단하지는 않는다) | 문서가 보존되지 않았다 = T1의 목적 미달성 |
| **(ii)만 실패** (`verify_failed` / `catalog_unparsed`) | **`CATALOG_PENDING`** | **통과** — 경고만 내고 **재차 block하지 않으며 블록 예산도 소모하지 않는다** | 문서는 이미 kompound에 보존·커밋됐다(§6.3.0). 카탈로그 지연은 사이클 완료를 막을 사유가 아니다 |

**`CATALOG_PENDING`의 확정 규칙 (D-1)** — 이 상태가 없으면 세 서술이 모순된다: "(ii) 실패는 예산을 소모하지 않는다" ↔ "`PENDING`으로 남아 다음 무장 시 이어받는다" ↔ 판정표의 "`pending ≥ 1` → block, `blocks += 1`". `PENDING`으로 남기면 다음 Stop에서 조건 4가 다시 성립해 **재차 block하며 예산을 태우고 3회 후 `GIVEN_UP`**이 되어 첫 서술이 거짓이 된다.

- **T1 판정에서 `CATALOG_PENDING`은 `DONE`과 동일하게 취급한다** — 통과, block 없음, 예산 미소모. 조건 4(`pending ≥ 1`) 평가보다 **앞서** 검사한다(그렇지 않으면 `pending`이 여전히 ≥1로 읽혀 block으로 흐른다).
- **카탈로그 재시도의 주체는 T1이 아니다.** 다음 사이클의 (ii) 실행, T2의 자동 박제, 또는 사용자의 수동 `apply`가 담당한다. F6 멱등에 의해 그때 (i)은 `unchanged` 무동작이고 (ii)만 재시도된다.
- `DONE`과 구별해 보존하는 이유는 **관측**이다 — §10.4-11(카탈로그 drift 누적)의 `catalog_lag_count`가 이 상태를 근거로 증가하고, T2 승계 경고가 이 상태를 읽어 "카탈로그가 뒤처져 있음"을 알린다(§5.2.3). `DONE`으로 덮으면 drift가 완전히 보이지 않게 된다.
- 상태 전이: `CATALOG_PENDING` → (카탈로그 성공) `DONE` / (새 사이클 무장) `PENDING`. STATE 서명이 바뀌면 새 사이클이므로 baseline과 함께 재평가된다.

**실패 경고의 사용자 도달 경로 (A-2, 확정)**

`stop-pipeline.sh`는 `exec python3 …`로 **stdout JSON만** 훅 프로토콜에 전달하고, Stop 훅의 stderr는 평시 사용자 화면에 나타나지 않는다. 즉 "stderr에 1회 경고"만으로는 T1의 실패가 조용히 사라진다(F11 위반). §10.3의 `gate_pass` 관측성 각주와 동일한 문제다.

- **채택: 런타임 상태 승계 노출.** `FAILED`(또는 `GIVEN_UP`) 상태를 런타임 상태 파일에 남기고, **T2 게이트가 다음 `git worktree remove`/`rm -r` 시 그것을 읽어 `gate_warn`으로 함께 출력**한다(`gate_warn`은 stderr 무조건 출력이며 PreToolUse stderr는 사용자에게 보인다). 추가 비용 0 — T2는 이미 같은 파일을 열 이유가 있다. 승계 출력 후 그 플래그는 소비(clear)해 반복 노출하지 않는다.
- **함께 문서화**: T1 자체의 stderr 경고는 **평시 비관측**이다. 이를 결함이 아니라 알려진 성질로 명시하고, 사용자에게 도달하는 경로는 ① T2 승계 노출 ② `HARNESS_DEBUG=1` 세션의 stderr ③ 런타임 상태 파일 직접 확인 세 가지뿐임을 밝힌다. write 실패 케이스는 상태를 남길 수 없으므로 ①도 불가하며 ②③만 남는다 — 이 최악 경로에서는 T1이 사실상 없는 것과 같고 방어가 T2 단독이 된다(T-l과 동일한 대가).

#### 5.1.4 서킷브레이커와의 조화 (F1 "영구 차단 금지")

**결정: 기존 서킷브레이커와 상태를 공유하지 않는다. 자체 `blocks` 카운터만 쓴다.**

> **원칙 (A-1): 예산을 기록할 수 없으면 예산을 소비하는 결정(block)을 내리지 않는다.**
> `blocks`가 지속되지 않는 상황에서 block을 반환하면 상한이 영원히 도달되지 않는다. 따라서 block 반환은 **런타임 상태 write 성공에 조건부**다 — 순서는 "판정 → 상태 write → (성공 시에만) block 반환"이며, write가 실패하면 `{"continue": True}`로 통과한다(§5.1.3 판정표).

- 자체 상한 `KOMPOUND_MAX_BLOCKS = 3` < 기존 `CB_MAX_BLOCKS = 20`. 따라서 **기존 서킷브레이커에 도달하기 전에 우리 게이트가 스스로 포기**한다. 이중 안전망은 `3 < 20`이라는 사실만으로 성립하고, 상태 공유는 필요하지 않다.
- `increment_breaker(state)`를 호출하지 **않는다.** 근거(리뷰 C-3): `increment_breaker`가 받는 `state`는 `decide()` Step 1(`stop-pipeline.py:348`)에서 로드되는데 우리 게이트는 Step 0 직후로 그보다 **앞**이다. 게다가 `/sdd-orchestrator` 직접 실행 시 `pipeline.json`이 없어 `state is None` → `increment_breaker(None)`이 `AttributeError` → `main()` L413-415 fail-safe → `{"continue": True}`. 즉 **T1의 주된 동기인 C3 케이스에서 게이트가 조용히 통과**한다. 연동을 제거하면 게이트는 `pipeline.json`의 존재에 전혀 의존하지 않는다.
- 우리 `blocks`는 런타임 상태 파일(`.claude/state/kompound-snapshot.json`)에 누적되며, 기존 브레이커의 TTL(5분) 리셋에 영향받지 않는다 → TTL 리셋을 이용한 무한 반복이 불가능하다.
- `blocks`는 `armed_session_id`가 바뀌면 초기화된다(§5.1.3). `GIVEN_UP`은 STATE 서명이 바뀌면(= 다음 사이클) 자동으로 초기화된다.
- 우리 게이트는 `pipeline.json`을 **읽지도 쓰지도 않는다**(워크트리 경로 힌트를 얻을 때만 존재하면 read-only로 참고). 따라서 기존 라벨 상태머신·브레이커·`atomic_write` 동작은 전부 불변이며 F17 안전망이 그대로 GREEN이다.

#### 5.1.5 SKILL.md 문서화 (F1 acceptance)

`skills/sdd-orchestrator/SKILL.md` Step 4의 2번과 3번 **사이**에 새 항목을 넣는다. 결과적으로 Step 4는 `result 생성 → STATE=COMPLETED → **kompound 박제** → push+pr-converge → 머지 승인 → worktree 정리`가 되고, Step 5(self-improve, L176~)보다 앞선 줄 번호에 위치한다(F1 acceptance의 "줄 번호" 검증 대상).

### 5.2 F2 — T2: PreToolUse 게이트

#### 5.2.1 확정 사항

| 항목 | 확정값 |
|---|---|
| 스크립트명 | `hooks/enforcement/kompound-snapshot-gate.sh` |
| hooks.json 등록 위치 | `PreToolUse` → `matcher: "Bash"` 배열의 **마지막**(`e2e-gate.sh` 다음) |
| 코어 호출 | `python3 -m hooks.lib.kompound_snapshot gate --command "$COMMAND" --json` |
| 차단 코드 | `exit 2` + `gate_block "KOMPOUND-SNAPSHOT-GATE" ...` |

**실행 순서 근거**: 우리 게이트는 python 기동 + (경우에 따라) 실제 박제·커밋까지 하는 이 배열에서 가장 비싼 항목이다. `dangerous-command`·`secret-detect`·`branch-gate`·`worktree-add-gate`·`e2e-gate`가 먼저 차단할 명령에 비용을 쓰지 않도록 마지막에 둔다. `worktree-add-gate.sh`와 **같은 블록**(F2 acceptance)이며 상호 간섭은 없다 — worktree-add-gate는 `git add`/`checkout`/`switch`만, 우리는 `git worktree remove`/`rm -r`만 본다.

#### 5.2.2 명령 파싱 규칙 (`wt_target`)

파싱은 **Python 코어**에 둔다. bash에는 프리필터만 남긴다(테스트 가능성 + 오탐 경계 관리).

**bash 프리필터** (비용 상한 §2.3):
```
case "$COMMAND" in
  *worktree*remove*|*rm\ -r*|*rm\ -f*|*--recursive*) ;;   # 계속
  *) exit 0 ;;                                             # python 미기동
esac
```
(`rm -f`를 포함하는 이유는 `rm -fr` 순서 변형을 잡기 위함이다. 정확 판정은 코어가 한다.)

**코어 파싱**:
1. 명령을 `;` `&&` `||` `|` 로 분해해 세그먼트별로 평가한다.
2. **패턴 A** — `git [-C <dir>] worktree remove [--force|-f] <path>`: 플래그가 아닌 마지막 토큰을 경로로 본다. `-C <dir>`이 있으면 상대경로를 그 디렉토리 기준으로 해석한다.
3. **패턴 B** — `rm` + 재귀 플래그(`-r` `-R` `-rf` `-fr` `-Rf` `--recursive`) + 경로 오퍼랜드 1개 이상.
4. **오퍼랜드가 워크트리인가**의 판정은 **이름이 아니라 사실**로 한다:
   - (a) 디렉토리이고 그 안의 `.git`이 **파일**이며 내용이 `gitdir:`로 시작 → linked worktree. (가장 강한 신호)
   - (b) 위가 아니지만 경로에 `worktrees/` 세그먼트가 있고 디렉토리로 존재 → 워크트리로 취급(`.git`이 이미 지워진 잔해 케이스).
   - 둘 다 아니면 **무개입**(exit 0).
5. 오퍼랜드가 존재하지 않으면 스캔 대상 0건 → 통과.

| 경계 | 판정 | 근거 |
|---|---|---|
| `rm -rf build/`, `rm -rf node_modules`, `rm -rf ~/.cache` | 무개입 | `.git` gitdir 파일 없음, `worktrees/` 없음 |
| `rm -rf /Users/x/repo/worktrees/foo` | 개입 | (a) 또는 (b) 성립 |
| `git worktree prune`, `git worktree list` | 무개입 | `remove` 아님 |
| `git worktree remove ../already-gone` | 통과(0건) | 경로 부재 |
| **미탐(수용)** `rm -rf $WT`, `rm -rf worktrees/*`, `cd <wt> && rm -rf .`, `find -delete`, python `shutil.rmtree` | 무개입 | 미확장 변수/글롭은 문자열에서 판정 불가. 잔여 위험은 T1이 흡수. 문서화 필수 |

변수 확장·`eval`은 **절대 하지 않는다**(게이트가 임의 명령을 실행하는 사고 방지).

#### 5.2.3 5개 분기 제어 흐름

```
tool_name != Bash                      → exit 0
COMMAND 프리필터 미통과                → exit 0                          [분기5: 무관 명령 무개입]
python3 없음 / 모듈 없음               → gate_warn + gate_pass + exit 0   [인프라 실패: 경고 후 통과]
코어 gate --json 실행
 ├ exit 0  · verdict=no_target         → gate_pass + exit 0              [분기5]
 ├ exit 0  · verdict=no_pending        → gate_pass + exit 0              [분기2: 0건]
 ├ exit 0  · verdict=snapshotted       → gate_warn(박제 목록) + gate_pass + exit 0  [분기3: 자동박제 성공]
 ├ exit 20 · verdict=disabled          → gate_warn(안내 1회) + gate_pass + exit 0   [분기1: F16 미설정]
 ├ exit 50 · verdict=verify_failed     → gate_warn(raw 보존됨 + 실패 게이트명) + gate_pass + exit 0
 ├ exit 55 · verdict=catalog_unparsed  → gate_warn(raw 보존됨 + 미인지 형상) + gate_pass + exit 0
 │            └─ 위 두 줄이 A-5의 축 3 — raw 복사가 끝났으므로 삭제를 막지 않는다
 ├ exit 30/40/45/60/70                 → gate_block(사유+수동 절차) + exit 2       [분기4: 실패 차단]
 └ 그 외 종료 코드(1,10,127,…)         → gate_warn + gate_pass + exit 0   [인프라 실패]
```

> 📌 종료 코드 표의 **단일 진실은 §6.2**다. `disabled`는 exit **20**이며(exit 0이 아니다) 게이트가 20을 명시적으로 통과 처리한다 — spec F2가 요구하는 "미설정 시 `gate_pass`"는 게이트의 매핑으로 달성되고, 코어는 "비활성"이라는 사실을 verdict/코드로 정직하게 보고한다. `gate` 서브커맨드는 **exit 10(`pending`)을 반환하지 않는다** — `pending ≥ 1`이면 자체적으로 `apply`까지 진행해 `snapshotted`(0) 또는 실패 코드(40/45/50/60/70)로 수렴하기 때문이다. 10이 나오면 계약 위반이므로 "그 외" 분기(경고 후 통과)로 떨어뜨린다.

**"조용한 통과 금지"의 구현**: 모든 통과 경로가 `gate_pass`를 호출한다(F2 acceptance). 추가로 사용자 눈에 보여야 하는 두 경로(disabled 안내·자동박제 성공)는 `gate_warn`(stderr 무조건 출력)을 쓴다 — `gate_pass`는 `HARNESS_DEBUG=1`에서만 출력되므로 그것만으로는 사람이 못 본다(§10.3 관측성 각주).

**T1 실패의 승계 노출 (A-2)**: `gate`는 위 판정 **전에** 런타임 상태(`.claude/state/kompound-snapshot.json`)의 `snapshot.status`를 읽고, 승계 대상 상태면 그 사유를 JSON `inherited_warning` 필드에 담는다. bash 게이트는 자기 verdict 처리와 **무관하게** 그 값이 있으면 `gate_warn`으로 먼저 출력하고, 출력 후 코어가 플래그를 소비(clear)해 반복 노출을 막는다. 이것이 평시 비관측인 T1 stderr를 사람에게 도달시키는 주 경로다.

| 상태 | 승계 | 문구 톤 |
|---|---|---|
| `FAILED` / `GIVEN_UP` | **승계** | **실패** — "T1 박제가 실패했다(사유). 문서가 보존되지 않았을 수 있다" |
| **`CATALOG_PENDING`** | **승계** | **정보** — "raw는 보존·커밋됐고 **카탈로그가 뒤처져 있다**(N 사이클). 삭제는 안전하다" |
| `DONE` / `PENDING` / `SKIPPED_UNCONFIGURED` | 승계 안 함 | — |

`CATALOG_PENDING`을 승계하되 **톤을 분리하는 이유**: 문서 소실 위험이 없으므로 `FAILED`와 같은 경고음을 내면 사용자가 두 상황을 구분하지 못하고, 반복되면 경고 자체가 무시된다. 그러나 완전히 침묵하면 §10.4-11의 drift가 보이지 않는다 — "안전하지만 뒤처졌다"가 정확한 메시지다.

**F9 선행 확인**: `gate` verdict 우선순위가 이를 보장한다 — `no_target` → `disabled` → `scan_error` → `unmapped_blocking` → `no_pending` → **`precondition_failed`(F9)** → `apply` 실행. 즉 F9가 걸리면 `apply`가 **호출조차 되지 않는다**(부작용 0, F2 acceptance).

**`apply` 2단 결과 → verdict 매핑 (A-5)**: `apply`는 (i) raw 복사 · (ii) 카탈로그 갱신(registry+index+log)의 2단이며 결과를 독립적으로 보고한다(§6.3.0).

| (i) raw | (ii) 카탈로그 | verdict | exit | T2 |
|---|---|---|---|---|
| 성공 | 성공 | `snapshotted` | 0 | 경고 후 통과 |
| 성공 | F8 게이트 실패 | `verify_failed` | 50 | **경고 후 통과** |
| 성공 | 형상 미인지/파싱 실패 | `catalog_unparsed` | **55** | **경고 후 통과** |
| **실패** | 미실행 | `write_failed` | 60 | **차단** |

**F2 acceptance의 5개 분기 — 분기 구조는 유지되고 분기3·4의 사유 집합이 재편됐다 (N-1 정밀화)**

개수(5개)와 각 분기의 통과/차단 성격은 그대로이지만 **소속이 변경**됐으므로, "그대로 유지"가 아니라 아래와 같이 정확히 기술한다.

| 분기 | 개정 전 | 개정 후 (A-5) |
|---|---|---|
| 1 미설정 통과 | 불변 | 불변 |
| 2 0건 통과 | 불변 | 불변 |
| **3 자동박제 성공 통과** | 전 파이프라인 성공 1경로 | **하위 분화** — ③-a 완전 성공(`snapshotted`) / ③-b **raw만 성공, 카탈로그 뒤처짐**(`verify_failed`·`catalog_unparsed`) |
| **4 자동박제 실패 차단** | F9 · **F8** · F12 · 경로 부재 | **사유 집합 재편** — F8이 **빠지고**(→ ③-b로 이동) **raw 복사 실패(`write_failed`)가 들어옴**. 남은 사유: `scan_error` · F9 · F12 · `write_failed` · `busy` |
| 5 무관 명령 무개입 | 불변 | 불변 |

통과·차단 각 경로가 `gate_pass`/`gate_block`을 거치는 계약은 불변이다. spec F2 acceptance의 "5개 분기 각각을 커버하는 테스트"는 ③이 ③-a·③-b 두 케이스로 늘어나는 형태로 충족된다.

**판정 집합은 하나, 정책만 둘 (B-6)**: T1과 T2는 동일한 코어 판정(`pending` / `unmapped` / F9 / F8)을 쓰고 **집합 계산에서 갈리지 않는다**. 갈리는 것은 그 결과에 대한 정책뿐이다 — T1은 `unmapped`를 무시하고(directive로 해소 불가), T2는 `unmapped_blocking`으로 차단한다(삭제되면 영구 소실). §1 원칙 1("단일 판정 구현")은 판정 로직의 단일성을 요구하는 것이고 정책의 동일성을 요구하지 않는다.

#### 5.2.4 차단인가 통과인가 — 3축 원칙 (A-5 승인 반영, 2026-07-29)

**원칙 (3축):**
1. **"문서가 위험하다고 판정됨" → 차단**
2. **"판정 자체를 못 했음" → 경고 후 통과**
3. **"카탈로그 갱신에 실패했음" → 경고 후 통과** — 문서는 이미 보존됐다

세 번째 축이 A-5의 핵심이다. **T2의 존재 이유는 "워크트리를 지워도 문서가 kompound에 남아 있는가"이며, raw 복사가 성공했다면 그 목적은 이미 달성됐다.** registry 파싱/카탈로그 갱신 실패는 "박제 대상 문서가 위험하다"가 아니라 "**카탈로그 갱신 방법을 모른다**"이고, 후자는 문서 소실 위험과 무관하므로 축 1을 적용할 근거가 없다. 개정 전 설계는 차단 기준을 "전 파이프라인 성공"으로 잡아 카탈로그 문제까지 삭제를 막았다 — **C-1과 동일한 구조의 함정**(부수적 정합성 실패가 사용자의 기본 작업을 영구히 막는다)이었다.

| 상황 | 결정 | 근거 |
|---|---|---|
| python3/모듈 부재, 예상 외 종료 코드, 타임아웃 | **경고 후 통과** (축 2) | F16 fail-safe. 이 기능이 고장 났다고 사용자가 워크트리를 영구히 못 지우게 되면 안 된다. 우회로가 없어 사용자가 갇힌다 |
| `scan_error` (exit 30) | **차단** (축 1) | "판정 실패"가 아니라 "**어떤 문서가 있는지 확인조차 못 했다**"는 확정 신호다. 삭제는 되돌릴 수 없다. F11의 "0건 vs 스캔 실패" 구분이 여기서 행동으로 갈린다 |
| `precondition_failed` — F9 dirty/diverge (exit 40) | **차단** (축 1) | raw 복사 자체를 시도할 수 없다 → 문서가 보존되지 않은 상태로 삭제된다 |
| `unmapped_blocking` — F12 (exit 45) | **차단** (축 1) | 프리픽스 미등록 문서는 박제 경로가 없다 → 삭제되면 영구 소실 |
| `write_failed` — **raw 복사 실패** (exit 60) | **차단** (축 1) | 정확히 "문서가 kompound에 없는 상태"다. T2가 막아야 하는 유일한 실패 |
| `verify_failed` — F8 검증 게이트 3종 (exit 50) | **경고 후 통과** (축 3) | 게이트 3종(링크 무결성·양방향 카운트·flat 유지)은 전부 **카탈로그 정합성** 검사다. 게이트가 잡는 것은 문서 소실이 아니라 **카탈로그 어긋남**이다 |
| `catalog_unparsed` — registry 표/카운트 형상 미인지 (exit **55**, 신규) | **경고 후 통과** (축 3) | raw는 이미 복사·커밋됐다. 카탈로그는 다음 실행에서 재시도한다 |
| `busy` — 락 획득 실패 (exit 70) | **차단** (축 1) | 판정을 못 한 상태이나 삭제가 비가역이라 보수적으로 막는다. 10분 stale 타임아웃이 있어 갇히지 않는다 |

차단 메시지에는 항상 **우회로**를 함께 낸다(수동 복사 절차 + `HARNESS_KOMPOUND_REPO`를 비워 기능을 끄는 방법). 사용자가 갇히지 않는다는 조건에서만 차단이 정당하다.

경고 후 통과(축 3) 메시지에는 **무엇이 보존됐고 무엇이 남았는지**를 반드시 함께 낸다 — "raw N건 복사·커밋 완료 / 카탈로그 갱신 실패(사유) → 다음 실행에서 재시도". 이것이 없으면 "조용한 통과"가 된다.

### 5.3 동시성

kompound 쓰기는 배타 락으로 직렬화한다: `os.open(<kompound>/.git/kompound-snapshot.lock, O_CREAT|O_EXCL)`. 획득 실패 시 verdict `busy`(exit 70). stale 락(mtime > 10분)은 무시하고 인수한다. T1은 `busy`를 "이번엔 판정 보류"로 처리해 상태를 갱신하지 않고 통과시킨다(다음 Stop에서 재시도). T2는 `busy`를 차단으로 처리한다(삭제 비가역성 때문).

### 5.4 수집 · 식별 · 네이밍 규칙 (F3 · F4 · F12)

트리거와 무관한 순수 데이터 변환 파이프라인이다. `scan → repo 식별 → naming → dedup` 순으로 흐르며 전 단계가 순수 함수(파일 read만)다.

#### 5.4.1 F3 — 스캔 (`scan.py`)

상수는 참고 구현(설계 SSOT L153-178)을 그대로 이식한다.

```
KINDS      = {"spec":"spec", "specs":"spec", "arch":"arch", "ui":"ui", "api":"api",
              "result":"result", "development":"arch", "context":"context"}
SKIP_DIRS  = {".git", "node_modules", "build", "ExternLib", ".venv", "venv"}
SKIP_NAMES = ("ORCHESTRATOR_STATE", "HANDOFF", "-GUIDE", "DESIGN.md", "test-guide-")
```

절차:

1. **앵커 탐색** — 각 스코프 루트에서 깊이 ≤ `max_anchor_depth`(기본 5)까지 순회하며 `docs/sdd` 또는 `Docs/sdd` 디렉토리를 수집한다. `SKIP_DIRS`는 이 단계에서도 프루닝한다. `*/worktrees/*`는 **프루닝하지 않는다**(워크트리 전용 문서가 실제로 존재 — F3).
2. **앵커 하위 전수 순회** — 앵커 아래는 깊이 제한 없이 순회한다. `SKIP_DIRS` 적용.
3. **kind 결정** — 앵커부터 현재 디렉토리까지의 세그먼트를 **역순으로** 훑어 `KINDS`에 먼저 걸리는 값을 채택(참고 구현의 `next((KINDS[x] for x in reversed(...)))` 동일). 없으면 그 디렉토리는 대상 아님.
4. **제외** — 경로에 `/task` 세그먼트가 있으면 스킵(`task/`·`tasks/` 동시 커버). 파일명이 `SKIP_NAMES` 중 하나를 포함하면 스킵. `.md`가 아니면 스킵.
5. **레코드 생성** — `{"kind", "path", "md5", "mtime", "repo_dir"}`. md5는 바이트 해시.
6. **오류 처리** — 개별 파일/디렉토리의 권한 오류는 `errors[]`에 누적하고 계속 진행한다. `errors`가 비어있지 않으면 최종 verdict는 `scan_error`(F11: "변경 없음"과 "스캔 실패"를 절대 같은 값으로 뭉치지 않는다).

#### 5.4.2 repo 식별 — `repo_dir` 도출 규칙 (확정)

`repo_dir`은 F4 프리픽스 조회와 F12 미등록 판정의 **유일한 입력**이므로 결정적으로 정의한다.

1. 앵커(`docs/sdd`)에서 **위로** 올라가며 각 조상 디렉토리를 검사한다.
2. 경로에 `worktrees` 세그먼트가 있으면 → **그 세그먼트의 부모**를 repo 루트로 채택하고 즉시 종료.
   예: `…/Marvelous_feature/worktrees/<wt>/docs/sdd/spec/x.md` → `Marvelous_feature`.
3. 그렇지 않으면 `.git`(디렉토리 **또는** `gitdir:` 파일)을 가진 첫 조상을 repo 루트로 채택. `.git`이 **`gitdir:` 파일**이면 그 내용을 파싱해 **본체 repo 루트를 도출**한다(B-4).
   - 파싱 규칙: `gitdir: <path>`의 `<path>`는 보통 `<main-repo>/.git/worktrees/<name>` 형태다. 경로에서 `/.git/worktrees/<name>` 접미사를 제거한 것이 본체 repo 루트다. 상대경로면 `.git` 파일이 있는 디렉토리 기준으로 해석한다.
   - 필요한 이유: 이 파싱이 없으면 `*/worktrees/*` 규약을 따르지 않는 **외부 위치 워크트리**(예: `/tmp/wt-foo`)가 규칙 2에 걸리지 않고 규칙 3에서도 자기 자신을 repo 루트로 잡아 **불필요하게 `unmapped`** 가 된다. `§5.2.2`가 T2 명령 파싱에서 이미 동일한 `gitdir:` 판정을 하므로 로직이 새로 늘지 않는다.
   - 파싱 실패(형식 불일치·경로 부재)면 규칙 4로 폴백한다(예외를 던지지 않는다).
4. 위 둘 다 실패하면(git 밖 디렉토리) → 스코프 루트 자신을 repo 루트로 본다.
5. **`prefix_map` 조회 키**는 채택된 repo 루트의 **디렉토리 이름**이다. 실패 시 한 단계 완화: `scan_root` 기준 상대경로의 **선두 1세그먼트 → 선두 2세그먼트를 `/`로 이은 값** 순으로 재조회한다.
   - 이 완화가 필요한 이유: registry L45-49가 `CLOFab_Web/clofab`을 home repo로 기록하듯, 한 repo 안의 하위 디렉토리가 독립 프로젝트처럼 문서를 갖는 경우가 실재한다. `CLOFab_Web/clofab/docs/sdd/...`는 규칙 3으로 `CLOFab_Web`(.git 소유자)에 도달하므로 기본 경로만으로 이미 정답이며, 완화 규칙은 `.git`이 하위에 별도로 있는 변형을 흡수한다.
6. **스캔 루트 밖 워크트리** — 스코프 루트가 `scan_root` 밖이어도 규칙 2·3은 `scan_root`와 무관하게 성립하므로 정상 식별된다. 5의 완화 규칙만 적용 불가(상대경로 계산 실패 → 건너뛴다). 즉 `scan_root`는 workspace 스코프의 순회 시작점일 뿐이며 식별의 전제가 아니다.

#### 5.4.3 F4 · F12 — 네이밍 (`naming.py`)

출력은 `raw/<project>-<feature>-<kind>.md`. 순수 함수 4단계:

1. **`<project>`** = `prefix_map[repo_dir]`. 조회 실패 또는 값이 `null`이면 → **미등록 신호 반환**(`{"unmapped": repo_dir}`), 예외를 던지지 않는다(F4 acceptance). 미등록 문서는 `pending`에 넣지 않고 `unmapped[]`로만 집계한다(§5.1.3, F12).
2. **`<kind>`** = `KINDS`의 디렉토리 매핑 결과(`spec|specs→spec`, `development→arch`, 그 외 동명).
3. **`<feature>`** = 원본 파일명(stem)에서 ① 날짜 프리픽스 `^\d{4}-\d{2}-\d{2}-` 제거 ② 접미사 `-spec`/`-dev`/`-result` 제거.
4. **프리픽스 중복 접기** — 결과가 `<project>-<project>-…` 꼴이면 하나를 접는다(`codegraph-codegraph-internal-mcp-result` → `codegraph-internal-mcp-result`).

기본 매핑 `DEFAULT_PREFIX_MAP`은 spec F4의 10종을 코드 상수로 갖고, 설정 `prefix_map`과 키 단위로 병합한다(§6.1).

#### 5.4.4 F5 — dedup (`dedup.py`)

`(kind, md5)`로 그룹핑 → 그룹 내 경로를 `key=lambda x: ("worktrees" in x, len(x))`로 정렬(참고 구현 동일) → 첫 번째를 canonical로 채택. 해시가 다르면 별개 문서로 취급하고 `mtime`이 더 최근인 것을 채택한다.

---

## 6. 영속화 · 직렬화 · IO 경계

### 6.1 F16 — 설정 해석 (확정)

**환경변수 (확정 키)**

| 키 | 의미 |
|---|---|
| `HARNESS_KOMPOUND_REPO` | kompound 저장소 절대경로 |
| `HARNESS_KOMPOUND_SCAN_ROOT` | 스캔 루트 절대경로 |
| `HARNESS_KOMPOUND_CONFIG` | 설정 파일 경로 직접 지정(테스트/오버라이드). 지정되면 ②의 탐색을 대체 |

`HARNESS_` 프리픽스는 `hooks/enforcement/lib/constants.sh`의 기존 네임스페이스와 일치시킨 것이다. `CLAUDE_*`는 Claude Code가 소유하는 네임스페이스라 침범하지 않는다.

**설정 파일 (확정 위치·형식)**

| 순서 | 경로 | 성격 |
|---|---|---|
| ②-a | `<project_root>/.claude/kompound-snapshot.config.json` | 프로젝트 오버라이드. 더 구체적이므로 먼저 |
| ②-b | `${CLAUDE_CONFIG_DIR:-~/.claude}/kompound-snapshot.json` | **주 저장소** — 머신 전역 |

> 📌 ②-a는 `.claude/state/` **밖**이다(`.claude/` 직속). `.claude/state/`는 이 문서가 스스로 "gitignore된 휘발성 상태 디렉토리라 설정 SSOT로 부적절"이라 판정한 자리이며(아래 후보 비교표), 런타임 상태 파일 `.claude/state/kompound-snapshot.json`과 이름·디렉토리가 혼동될 위험도 있다. 설정(사람이 쓰는 입력)과 런타임 상태(코어가 쓰는 출력)를 디렉토리로 분리한다.

형식은 **JSON**(stdlib `json`, 게이트에서 `jq` 가용, `e2e-config.json` 선례. YAML은 외부 의존이라 배제):

```json
{
  "schema_version": 1,
  "kompound_repo": "<abs path>",
  "scan_root": "<abs path>",
  "max_anchor_depth": 5,
  "state_max_age_hours": 24,
  "prefix_map": { "<repo dir name>": "<prefix>", "<repo dir name>": null }
}
```

**위치 후보 비교와 채택 근거**

| 후보 | 판정 | 근거 |
|---|---|---|
| `<project>/.claude/` 단독 | 보조로만 채택 | 스캔 루트·kompound 경로는 **머신 전역 값**인데 SDD를 돌리는 모든 repo마다 사본이 생긴다. 특히 `.claude/state/`는 gitignore된 휘발성 상태 디렉토리라 설정 SSOT로는 부적절(그래서 ②-a는 `state/` 밖에 둔다). 단 테스트 주입·프로젝트별 예외에는 유용 → ②-a로 유지 |
| 하네스 플러그인 디렉토리 | **배제** | 플러그인은 마켓플레이스로 배포되는 git 추적 산출물이다. 사용자 고유 절대경로를 여기 쓰면 커밋되어 F16의 금지 사항 자체를 위반한다 |
| repo 루트 `CLAUDE.local.md` 발견 | **배제** | 빌드 프로파일 선례는 "사람이 읽는 *명령*의 발견"이고 기계가 파싱하는 구조적 설정이 아니다. 프롬프트 파일에 설정을 섞으면 마크다운 파서가 하나 더 늘고, 여전히 per-project다 |
| 사용자 홈 `~/.claude/` | **주 저장소 채택** | 머신 전역 · 어떤 repo에도 커밋되지 않음 · `~/.claude/CLAUDE.md` 등 사용자 전역 설정의 기존 자리. `CLAUDE_CONFIG_DIR`을 존중해 다중 계정 운영(사용자 실제 환경)에서도 격리된다 |

**병합 규칙 (확정) — 파일 우선이 아니라 키 단위 우선이다.**

우선순위: **env > ②-a 프로젝트 파일 > ②-b 홈 파일 > 자동 탐색 > 코드 기본값.** 해석은 "첫 소스가 이기는(first-wins-file)" 방식이 아니라 **키 단위 병합**이다.

| 필드 | 병합 방식 |
|---|---|
| `kompound_repo` · `scan_root` · `max_anchor_depth` · `state_max_age_hours` (스칼라) | 가장 높은 우선순위에서 **값이 존재하는(non-null)** 소스의 값을 채택 |
| `prefix_map` (dict) | 낮은 우선순위 → 높은 우선순위 순으로 **dict 병합**. 값이 `null`이면 그 키를 **삭제**(= 미등록으로 되돌림, F12 경로) |

> 📌 file-first-wins를 쓰면 안 되는 이유(J-10): `{"max_anchor_depth": 3}` 하나만 담은 프로젝트 파일이 홈 파일 전체를 가려 `kompound_repo`가 사라지고 **기능이 조용히 비활성**된다. 키 단위 병합이면 프로젝트 파일은 자신이 명시한 키만 덮는다.

**프리픽스 매핑**의 기본 10종은 `naming.py`의 상수 테이블(`DEFAULT_PREFIX_MAP`)로 코드에 두고 위 dict 병합의 최하위 소스로 참여한다. 전체 교체 모드 같은 추가 노브는 두지 않는다.

`resolve_config()`은 결과에 `source` 맵(`{"kompound_repo": "env|project|home|discovery", ...}`)을 함께 반환하고 리포트에 싣는다 — "어디서 온 값인지"가 보이지 않으면 조용한 오설정을 진단할 수 없다.

**③ 자동 탐색 알고리즘** (무엇을 어디까지 찾는가 — 이름 하드코딩 금지)

1. 후보 디렉토리 집합 = `<project_root>`의 **부모 디렉토리의 직속 자식**(1단계만). 근거: SDD를 돌리는 repo와 kompound는 같은 워크스페이스의 형제다.
2. 각 후보를 **kompound 서명**으로 검증: ① git 저장소(`.git` 존재) ② `raw/` 디렉토리 존재 ③ `wiki/index.md` 존재 ④ `wiki/log.md` 존재. (AGENTS.md가 규정한 kompound의 필수 구조 — 이름이 아니라 구조로 식별한다.)
3. 서명 통과 후보가 **정확히 1개**면 채택. **0개 또는 2개 이상이면 미해석**(추측하지 않는다).
4. 스캔 루트 = 채택된 kompound의 부모 디렉토리. 그 값이 `/` 또는 사용자 홈 자체면 거부.
5. 탐색 결과는 캐시하지 않는다(디렉토리 1회 나열 + stat 몇 번이라 저렴하고, 캐시는 stale 위험만 만든다).

**해석 실패의 의미 분리**: `kompound_repo` 미해석 → **기능 비활성**(F16). `scan_root` 미해석 → 비활성이 아니라 **workspace 스코프만 사용 불가**(T1·T2는 repo/worktree 스코프를 쓰므로 정상 작동). spec F16이 비활성 조건으로 kompound 경로만 지목한 것과 일치한다.

**④ 미설정 안내 "1회"의 기억 위치 (확정)**

**소유 모듈은 `runtime_state.py` 하나다.** `config.py`는 "미설정"이라는 사실만 결과 dict로 반환하고 안내 출력 여부를 판단하지 않는다 — 책임이 두 모듈로 갈리면 어느 쪽이 억제 중인지 추적할 수 없다(M-18). `runtime_state.should_emit_unconfigured_notice()`가 유일한 판정 지점이다.

| 층 | 구현 | 보장 |
|---|---|---|
| 프로세스 내 | `runtime_state` 모듈 레벨 플래그. 한 프로세스에서 몇 번 물어도 `True`는 1회 | F16 acceptance("동일 실행 내 정확히 1회")를 직접 검증 가능 |
| 호출 간 | `.claude/state/kompound-snapshot.json` 의 `notice = {"session_id", "at"}`. **동일 `CLAUDE_SESSION_ID`에 1회.** session id를 못 얻으면 `at` 기준 **24시간 창** | 매 Bash 명령마다 떠드는 소음(PreToolUse!) 방지 + 영구 침묵(F11의 조용한 실패) 방지 |

즉 **영구 침묵도, 매번 떠들기도 아니다.** 세션이 바뀌거나 하루가 지나면 다시 한 번 알린다. 안내 억제 중에도 `gate_pass` 로그 호출은 매번 이루어지므로 감사 흔적은 끊기지 않는다.

### 6.2 CLI 계약 (확정)

**호출 형태**: `python3 -m hooks.lib.kompound_snapshot <subcommand> [opts]` (`PYTHONPATH=<plugin root>`).
`hooks/`·`hooks/lib/`는 `__init__.py`가 없는 implicit namespace package이고 기존 테스트가 `hooks.lib.self_improve.*`를 그렇게 import하므로 동일 방식이 성립한다. `cli.py`는 `build_parser()` / `main(argv=None)`을 노출해 서브프로세스 없이도 단위 테스트된다(`evals/run_eval.py` 관례).

| 서브커맨드 | 부작용 | 소비자 | 주요 옵션 |
|---|---|---|---|
| `check` | **없음(read-only)** | T1, T2 내부, 사람 | `--scope-root PATH`(반복), `--scope=workspace`, `--json` |
| `apply` | **2단**: (i) raw write + 커밋 → (ii) 카탈로그 write + 커밋 | T1 directive, 사람 | `--scope-root`, `--scope=workspace`, `--json` |
| `gate` | 조건부(내부적으로 check→apply) | T2 게이트 | `--command STR`, `--json` |

`check`가 spec D4/F2의 "부작용 없는 확인 모드"를 구현한다. spec이 플래그 이름을 `--check`로 표기했더라도 계약은 "부작용 없음"이며, 서브커맨드 형태가 argparse 관례상 더 명확하다. 하위 호환용 별칭 `--check`는 두지 않는다(노브 최소화).

**종료 코드 규약 (전 서브커맨드 공통 — 이 표가 단일 진실이다. §5.2.3의 분기표는 이 표에서 파생된다)**

| 코드 | verdict | 단계 | 의미 | T2 |
|---|---|---|---|---|
| 0 | `ok_no_pending` / `snapshotted` / `no_target` | — | 할 일 없음 또는 (i)(ii) 모두 성공 | 통과 |
| 10 | `pending` | — | 매핑된 미박제 ≥1 (**`check` 전용** — `gate`·`apply`는 이 코드를 반환하지 않는다) | (해당 없음) |
| 20 | `disabled` | — | kompound 미설정 (F16) | 통과 |
| 30 | `scan_error` | 스캔 | 스캔/예외 실패 (F11) | **차단** |
| 40 | `precondition_failed` | 사전 | kompound dirty/diverge (F9) | **차단** |
| 45 | `unmapped_blocking` | 사전 | 삭제 대상 스코프에 미등록 프리픽스 문서 존재 (F12+F2) | **차단** |
| 50 | `verify_failed` | **(ii)** | 검증 게이트 3종 중 실패 (F8) — **카탈로그 정합성** | 통과(경고) |
| **55** | **`catalog_unparsed`** | **(ii)** | registry 표 형상·카운트 문장 미인지 등 카탈로그 갱신 불가 (신규, A-5) | 통과(경고) |
| 60 | `write_failed` | **(i)** | **raw 복사/커밋 실패** — 문서가 kompound에 없다 | **차단** |
| 70 | `busy` | 락 | 배타 락 획득 실패 | **차단** |

`1`·`2`는 코어 verdict로 쓰지 않는다(게이트의 `exit 2`, 파이썬 기본 오류와 충돌 방지).

> 📌 **단계 열이 T2 정책을 결정한다(A-5).** (i) 단계 실패와 그 이전(스캔·사전·락)만 차단이고, **(ii) 단계 실패는 전부 통과**다. `50`은 개정 전 차단이었으나 F8 게이트 3종이 전부 카탈로그 정합성 검사임이 확인되어 (ii)로 재분류됐다. 새 verdict를 추가할 때는 **어느 단계의 실패인가**를 먼저 정하면 T2 정책이 자동으로 결정된다.

**stdout / stderr 분리 (확정)**

| 모드 | stdout | stderr |
|---|---|---|
| `--json` (게이트·훅) | 한 줄 JSON (기계 파싱 전용) | 사람이 읽는 리포트 |
| 기본 (사람) | 사람이 읽는 리포트 | 경고만 |

JSON 스키마(고정 키):

```
{
  "verdict", "exit_code", "config_source", "scope_roots", "anchors",
  "raw_stage":     {"ok": bool, "new": [], "updated": [], "unchanged": N,
                    "committed": bool, "commit": "<sha|null>", "error": ""},
  "catalog_stage": {"ok": bool, "attempted": bool, "registry": bool, "index": bool,
                    "log": bool, "committed": bool, "commit": "<sha|null>",
                    "failed_gates": [], "unparsed": "<사유|null>", "error": ""},
  "unmapped": [], "pending": [], "dirty": [], "errors": [],
  "runtime_status": "PENDING|CATALOG_PENDING|DONE|SKIPPED_UNCONFIGURED|FAILED|GIVEN_UP",
  "catalog_lag_count": N,
  "inherited_warning": {"kind": "failure|info|null", "text": "..."},
  "human": "..."
}
```

`runtime_status`의 값 집합은 §5.1.2의 상태 값 목록과 **동일해야 한다**(단일 진실은 §5.1.2). `inherited_warning`은 문자열이 아니라 `{kind, text}` 객체다 — T2가 `FAILED`(실패 톤)와 `CATALOG_PENDING`(정보 톤)을 구분해 출력해야 하기 때문이다(§5.2.3).

**2단 결과는 반드시 독립 필드로 담는다(A-5).** `raw_stage.ok=true` + `catalog_stage.ok=false`가 "문서는 보존됐고 카탈로그만 뒤처졌다"를 표현하는 유일한 방법이며, 이 구분이 T2 정책(차단 vs 경고 통과)과 T1 정책(실패 보고 vs `pending` 유지)을 동시에 결정한다. 두 단계를 단일 `ok`로 합치면 A-5 이전의 함정으로 되돌아간다.
`new`/`updated`가 0이고 `errors`가 비어 있으면 "변경 없음", `errors`가 있으면 "스캔 실패" — 두 상태의 verdict가 다르므로 문자열로 뭉뚱그려지지 않는다(F11).

`pending[]`과 `unmapped[]`는 **서로 배타적인 집합**이다(§5.1.3, J-11): `pending`은 프리픽스가 매핑된 미박제 문서, `unmapped`는 프리픽스 미등록으로 박제 자체가 불가한 문서. 두 카운터를 합치면 T1의 directive가 해소 불가능해지고, 분리하면 T1은 `pending`만 보고 T2는 둘 다 본다.

### 6.3 F6/F7/F10 — 쓰기 형태 규율

- **raw 복사는 verbatim**(바이트 그대로). 없으면 신규 / 같으면 무동작·무로그 / 다르면 덮어쓰기(F6).
- **registry는 재생성하지 않고 외과적으로 수정한다.** 허용 연산 3개뿐: ① 행 추가 ② 셀의 `—` → 링크 교체(및 `기타` 열의 ` · ` 합성) ③ **열거된** 카운트 문장 갱신(§6.3.3). 그 외 줄은 바이트 단위로 보존한다. 표 스키마가 heterogeneous(§6.3.2)라 파서가 열 역할을 헤더 라벨로 추론하고, **추론 실패 시 추측하지 않고 실패 보고**한다(verdict `catalog_unparsed` — **카탈로그 커밋만 없고 raw는 유지·커밋된다**, §6.3.0).
- **F10 "양쪽 보존"은 쓰기 형태로 구현한다.** `log.md`는 append-only, `index.md` 최근 변경은 prepend-only, 기존 줄은 수정하지 않는다. 이 형태이면 git 병합 충돌이 나도 양쪽 보존이 기계적으로 성립한다. 여기에 F9(dirty면 중단)가 결합해 사람의 미커밋 편집을 덮어쓸 경로가 없다.
- `index.md` Entries의 `sdd-spec-registry` 훅 문장은 그 한 줄만 교체 대상이다(카운트 갱신). Entries의 다른 줄과 `미해결 모순` 섹션은 건드리지 않는다.
- **트랜잭션 저널 + 부분 롤백**: `apply`는 쓰기 전에 (경로, 존재여부, 원본 바이트) 저널을 **단계별로** 만든다. F8 검증 실패·카탈로그 파싱 실패 시 **(ii) 단계의 저널만** 되돌리고 **(i) raw는 유지·커밋**한다 — 상세는 §6.3.0.

#### 6.3.0 `apply` 2단 분리와 커밋 경계 (A-5 승인 반영, 2026-07-29)

`apply`를 독립적인 두 단계로 쪼갠다. 이 분리가 A-5의 구조적 토대다.

| 단계 | 내용 | 커밋 | 실패 시 |
|---|---|---|---|
| **(i) raw 복사** | canonical 문서를 `raw/<project>-<feature>-<kind>.md`로 verbatim 복사(F6 멱등) | **성공 즉시 raw만 커밋** (`snapshot(raw): N new, M updated`) | `write_failed`(60). 저널로 전량 롤백. **T2 차단 / T1 실패 보고** |
| **(ii) 카탈로그 갱신** | registry(§6.3.2·§6.3.3) + `index.md` + `log.md` 갱신 → F8 게이트 3종 → 커밋 | 게이트 통과 시 커밋 (`snapshot(catalog): …`) | `verify_failed`(50) / `catalog_unparsed`(55). **(ii) 저널만 롤백, (i)은 유지.** **T2 통과(경고) / T1 경고 + `pending` 유지** |

**커밋을 2개로 나누는 이유 — F9 자기 오염 회피.** (ii)가 실패했을 때 raw를 워킹트리에 미커밋 상태로 남기면 kompound가 dirty가 되고, **다음 실행이 우리가 만든 dirty 때문에 F9(exit 40)로 막힌다**. 그러면 카탈로그를 영원히 재시도할 수 없다. 그래서 (i) 성공 직후 raw를 커밋해 **워킹트리를 항상 clean하게 유지**하고, 카탈로그는 다음 실행에서 이어받는다. 즉:

- (ii) 실패 후의 kompound 상태 = **raw는 커밋됨 + 카탈로그는 이전 상태** → clean, F9 통과, 재시도 가능.
- 다음 실행의 (i)은 F6 멱등에 의해 `unchanged`로 무동작하고, (ii)만 다시 시도된다. **재시도가 자연히 이어진다.**

> 📌 T-c(롤백 강화)의 결론이 A-5로 **조정**됐다. 개정 전에는 verify 실패 시 raw까지 되돌렸는데, 그러면 "문서가 kompound에 없는 상태"를 스스로 만들고 그 결과로 T2 차단이 사후 정당화되는 순환이 생긴다. 이제 롤백 범위는 **(ii) 카탈로그 변경으로 한정**한다. "실패하면 커밋하지 않는다"(F8)는 요구는 **카탈로그 커밋에 대해** 그대로 지켜진다.

**F7 "배치 1건 = 로그 1줄"과의 관계 (AGENTS.md Bulk Ingest 규칙)**

(ii)가 실패한 배치는 **`log.md` 줄이 없는 상태로 남는다.** 이것이 AGENTS.md 규칙 위반이 아닌 근거:

- AGENTS.md가 금지하는 것은 **한 배치가 여러 줄로 흩어지는 것**(소스별 N줄 append)이다. "아직 줄이 없다"는 그 규칙의 위반이 아니다 — 로그는 append-only 원장이고, 기록되지 않은 작업은 원장에 없는 것이 정상이다.
- 다음 실행에서 (ii)가 성공하면 **그때 1줄만** append된다. raw 커밋과 카탈로그 커밋이 서로 다른 시점이 되었으므로 그 줄은 **두 시점을 함께 표기**한다:
  `YYYY-MM-DD [snapshot] <N raw> — raw 커밋 <sha7>(YYYY-MM-DD) · 카탈로그 <sha7>(YYYY-MM-DD) · 재시도 K회`
  이렇게 하면 "언제 문서가 보존됐는지"와 "언제 카탈로그가 따라왔는지"가 원장 한 줄에서 모두 읽힌다 — 배치 1건 = 1줄을 유지하면서 정보 손실도 없다.
- **"배치"의 정의가 이동한다는 점을 명시한다(N-2).** 평시 배치 = `apply` 1회다. 그러나 (ii)가 여러 번 연속 실패한 뒤 카탈로그가 한 번에 성공하면, 그 1줄이 대표하는 단위는 **"카탈로그 성공 1회"** 가 된다(= 그동안 누적된 raw 커밋 K개를 함께 기록). 정의가 *apply 1회* → *카탈로그 성공 1회*로 넓어지는 것이다.
  - AGENTS.md Bulk Ingest 규칙의 **목적은 단편화 방지**(한 논리적 작업이 N줄로 흩어지는 것)이므로 이 이동은 규칙 위반이 아니라 규칙의 목적에 더 부합한다 — 만약 raw 커밋마다 1줄을 남기려 하면 카탈로그가 없는 상태에서 K줄이 흩어지고, 그것이 정확히 규칙이 금지하는 형태다.
  - **요구사항**: 그 1줄은 자신이 대표하는 **raw 커밋 sha를 전부 열거**해야 한다(누락 금지). 예:
    `YYYY-MM-DD [snapshot] <총 N raw> — raw 커밋 <sha7>(날짜)·<sha7>(날짜)·<sha7>(날짜) · 카탈로그 <sha7>(날짜) · 재시도 K회`
  - 열거가 없으면 "언제 무엇이 보존됐는지"가 원장에서 소실되어 raw 커밋들이 고아가 된다.

#### 6.3.1 SDD 스냅샷 raw 집합의 정의 — F8 게이트(2)의 전제 [CRITICAL 대응]

**실측 (2026-07-29, `/Users/moon/workspace/marvelous_kompound`):**

| 측정 | 값 |
|---|---|
| registry가 가리키는 `../raw/*.md` 링크 중 SDD kind 문서 | **117** |
| `raw/` 안에서 파일명이 kind 접미사(`-spec`/`-arch`/`-ui`/`-api`/`-context`/`-result`)로 끝나는 파일 | **122** |
| 위 두 집합의 차 | **5 → 게이트(2)가 항상 실패** |
| 초과 5건 | `clocv-wasm-api-expansion-spec` · `fabric-creator-web-api-spec` · `gps-html-to-ui` · `mvcv-refactor-lock-fixture-spec` · `pattern-api-json-external-spec` — 사람이 독립 `/ingest`한 주제 문서가 우연히 kind 접미사로 끝난 것 |
| **프리픽스 매핑 ∩ kind 접미사**로 한정한 집합 | **117** — registry 링크와 양방향 차집합 **0, 정확히 통과** |

즉 "kind 접미사로 끝나는 raw 파일"을 SDD 스냅샷 집합으로 정의하면 **feature를 켜는 순간 F8 게이트(2)가 오늘 이미 실패**한다. 개정 전 설계에서는 그것이 `verify_failed` → raw까지 롤백 → `exit 50` → **T2가 모든 `git worktree remove`를 매번 차단**으로 연쇄됐다(T1은 3회 후 `GIVEN_UP`) — 첫 실행에서 사용자가 워크트리를 지울 수 없게 되는 치명적 결함이었다.

> 📌 **A-5가 이 연쇄를 이중으로 차단한다(방어 심층화).** 이제 `verify_failed`는 (ii) 단계 실패이므로 raw는 보존·커밋되고 T2는 경고 후 통과한다(§6.3.0, §5.2.4 축 3). 그래도 **`snapshot_set_rule`은 여전히 필수**다 — A-5는 "게이트가 틀렸을 때의 피해"를 낮췄을 뿐이고, 규칙이 없으면 카탈로그가 **영구히 한 사이클도 갱신되지 못한다**(매 실행 `verify_failed`). 두 수정은 대체 관계가 아니라 보완 관계다.

**따라서 `verify.py`의 계약에 `snapshot_set_rule`을 명시한다:**

```
snapshot_set_rule:
  raw/<P>-<feature>-<kind>.md  where
    P    ∈ prefix_map.values()  (설정 병합 후의 유효 프리픽스 집합, null 제거)
    kind ∈ {spec, arch, ui, api, context, result}
```

- 이 규칙을 만족하는 `raw/*.md`만 **SDD 스냅샷 집합**이며, F8 게이트 (1)(2)(3)은 이 집합에 대해서만 판정한다.
- 규칙 밖의 `raw/*.md`(사람이 `/ingest`한 주제 문서·설계 SSOT 등)는 **집합 밖**이므로 카운트에 포함되지 않고, 훅은 그 파일을 읽지도 쓰지도 않는다.
- 게이트(2)의 정확한 정의: `registry가 가리키는 스냅샷 집합 링크` 와 `raw/에서 규칙을 만족하는 파일` 의 **양방향 차집합이 0**. 단순 개수 비교가 아니다 — 개수는 같고 내용이 어긋나는 경우를 놓친다.
- `prefix_map`이 설정으로 확장되면 집합의 경계도 함께 움직인다. 그래서 게이트 리포트에 사용된 프리픽스 목록을 항상 함께 출력한다(경계가 보이지 않으면 카운트 불일치를 진단할 수 없다).

> 📌 spec F8도 같은 내용으로 수정 중이다(S-2). 두 문서의 정의가 갈리면 게이트가 오늘의 실패 상태로 되돌아간다.

#### 6.3.2 F7 — registry 표 탐색과 행/열 삽입 (확정 — 사용자 승인 2026-07-29)

실측된 표 형상 3종이 공존한다: (a) 7열 `feature|spec|arch|기타|result|기존 위키|home repo`(Marvelous·CLOFab_Web), (b) `기타`가 없는 6열(auto-fix-orchestrator), (c) `프로젝트` 열이 선행하는 8열 통합표(그 외 프로젝트). `moon-harness`는 **자기 표가 없고 (c)의 행으로 존재**한다(registry L75-77).

→ F7의 "프로젝트 표 자체가 없으면 표 신설"을 문자대로 적용하면 `moon-harness` feature를 넣을 때 **새 표를 신설해 registry가 분열**한다(같은 프로젝트가 두 곳에). 그래서 탐색 규칙을 3단으로 확정한다:

| 단계 | 규칙 | 결과 |
|---|---|---|
| ① | 섹션 헤딩(`### …`) 텍스트가 프로젝트명을 포함하는 표를 찾는다 | 있으면 그 표에 행 추가 |
| ② | 없으면 `프로젝트` 열을 가진 표에서 그 값이 **이미 존재하는** 행을 찾는다 | 있으면 **그 표에** 행 추가(같은 프로젝트 행들 바로 뒤에 삽입) |
| ③ | ①②가 모두 실패할 때만 | 새 `### <프로젝트>` 섹션 + **7열 형상 (a)** 표를 `## 결정과 근거` 바로 앞에 신설 |

> 📌 **①②가 ③보다 앞서는 것이 사용자 결정("분류에 속하지 않으면 새로 만드는 게 맞다")과 충돌하지 않는다.** ②는 "이미 그 표에 귀속돼 있는 기존 프로젝트"만 잡는다 — `moon-harness`는 새 프로젝트가 아니라 8열 통합 표에 이미 3행(L75-77)으로 존재하므로 ②에서 그 표로 귀속되는 것이 정답이다. **진짜 새 프로젝트는 ①②에 걸릴 데이터가 없으므로 반드시 ③으로 신설된다.** 즉 규칙은 "기존 것은 제자리에, 새 것은 새로"를 그대로 구현한다.

- **행 삽입 위치**: 대상 표의 마지막 행 뒤(①·③) 또는 동일 프로젝트 행 그룹의 마지막 뒤(②). 기존 행 순서는 재정렬하지 않는다.
- **열 채우기**: `기존 위키` 열은 사람 지식이므로 항상 `—`. `home repo` 열은 `repo_dir`(+ 워크트리 사본이 있으면 ` + \`worktrees/<wt>\``).
- **없는 kind 열은 추가한다 (사용자 승인 2026-07-29 — 방향 반전).** `기타` 열이 없는 형상(b)에 `ui`/`api`/`context`가 생기면 **열을 추가하고 기존 행의 그 칸을 `—`로 채운다.**
  - 근거: 사용자 원칙("분류에 속하지 않으면 새로 만든다")의 일관된 확장이다. 개정 전 결정(실패 보고)으로 두면 **그 프로젝트의 카탈로그가 영구히 갱신 불가**가 된다 — 새 kind가 나올 때마다 매번 같은 지점에서 막힌다. 열 추가는 기존 행의 데이터를 훼손하지 않으며, `—`는 registry 범례(L17 "범례: ✓=있음, —=산출물 없음")상 **사실 그대로**의 표기다. A-5로 이 조작의 위험은 이미 "카탈로그 1사이클 뒤처짐" 수준으로 내려가 있다.
  - **안전 조건 (둘 다 만족할 때만 열 추가)**: (a) 추가할 kind가 6종(`spec`·`arch`·`ui`·`api`·`context`·`result`) 안에 있다. (b) 대상 표의 헤더 구조가 인지된 3형상 (a)/(b)/(c) 중 하나다.
  - 안전 조건을 만족하지 못하는 형상에서는 열을 추가하지 않고 `catalog_unparsed`(exit 55) → **경고 후 통과**다(§5.2.4 축 3). 즉 최악의 경우에도 raw는 보존되고 삭제 흐름은 막히지 않는다.
  - 열 삽입 위치: 형상 (a)의 열 순서(`feature|spec|arch|기타|result|기존 위키|home repo`)를 기준으로 **그 순서상 제자리**에 넣는다(`기타`는 `arch` 뒤·`result` 앞). 헤더 구분선(`|---|:--:|…`)도 같은 위치에 정렬 표기를 삽입한다.
  - 열 추가는 **표 하나에 국한**한다. 다른 프로젝트 표를 함께 고치지 않는다(F7 "3파일만·최소 변경").

**registry 쓰기의 근거는 registry 자신의 배너다 (N-3)**

`sdd-spec-registry.md` L1에는 AGENT 배너가 있다:

> `<!-- AGENT: do not Edit/Write this file directly. This wiki page is a derived registry of raw/ SDD snapshots. To add/refresh entries, copy the source docs into raw/<project>-<feature>-{spec,arch,ui,api,context,result}.md and re-run the SDD-spec ingest, then update this page. Direct content edits will drift from raw/. index.md / log.md remain operationally maintained. -->`

- 배너가 금지하는 것은 **raw 없이 이 페이지를 직접 고치는 것**이고, 승인하는 절차는 **"raw로 복사 → 그 다음 이 페이지를 갱신"** 이다. 이 훅의 흐름((i) raw 복사 → (ii) 카탈로그 갱신, §6.3.0)은 배너가 기술한 절차와 정확히 동일하다. 즉 **훅의 registry 쓰기 근거는 배너 자신**이며, 훅은 배너를 우회하는 것이 아니라 배너가 사람에게 요구하던 절차를 기계화한 것이다.
- **열 추가는 "add/refresh entries"보다 한 단계 위인 스키마 변경**이다. 그럼에도 SSOT를 깨지 않는 근거: 새 kind 열의 존재 자체가 `raw/`에 그 kind 파일이 생겼다는 사실에서 **파생**되므로 raw↔registry drift를 만들지 않는다(registry는 여전히 raw의 파생 카탈로그다). 여기에 §7의 "wiki 3파일 외 무수정"이 지켜지고, 안전 조건 2개(kind 6종 이내 · 인지된 3형상 이내)로 조작 범위가 유계다.
- **헤딩 매칭 규칙 (A-3 정정)**: 프로젝트명 ↔ 섹션 헤딩 매칭은 `prefix_map`의 키(repo 디렉토리명)와 값(프리픽스) **양쪽을 후보로** 쓰고, 판정은 **대소문자 무시 부분 일치**다. 모호 판정의 기준은 **후보 개수가 아니라 매칭된 섹션 개수**다 — **매칭되는 섹션이 2개 이상일 때만** 모호로 보고 실패 보고한다.
  - 근거 1(실측): registry L38 헤딩은 `### CLOFab_Web (clofab 웹 뷰어 / WASM)`이다. `repo_dir = CLOFab_Web`의 후보 2개(키 `CLOFab_Web`, 값 `clofab`)가 **둘 다 이 하나의 헤딩에 부분 일치**한다. "후보 2개 이상 → 모호"로 판정하면 **CLOFab_Web feature는 영구히 실패**한다. 여러 후보가 같은 섹션을 가리키는 것은 모호가 아니라 **합치**다.
  - 근거 2(실측): `repo_dir = Marvelous_dev`(값 `marvelous`)는 `### Marvelous (CLO C++ 엔진 …)` 헤딩에 **대소문자 무시에서만** 걸린다. registry L27이 실제로 `segment-topstitch-cpx-json`(Marvelous_dev 유래)을 `### Marvelous` 표에 두었으므로 대소문자 무시가 정답이다.
  - 서로 다른 두 섹션이 매칭되는 경우(예: 향후 `### Marvelous`와 `### Marvelous_graphify`가 `marvelous` 후보에 동시 걸림)에만 실패 보고한다. 이 충돌은 **가장 긴 매칭 문자열을 가진 섹션 우선**으로 1차 해소하고, 그래도 동률이면 실패 보고한다.

#### 6.3.3 F7 — 카운트 문장 갱신 범위 (열거, 확정)

registry에는 카운트가 **3~5곳**에 흩어져 있고 전부 갱신 대상이 아니다. 날짜가 박힌 스냅샷 서술을 고치면 **사실 왜곡**이 된다.

| 위치 | 예 | 처리 |
|---|---|---|
| `## 현재 상태` 아래 첫 문장 | `40 feature · raw 117개(spec 40 · arch 36 · result 28 · api 5 · ui 4 · context 4)` | **갱신** — 총계 + kind별 분해 모두 |
| `관련 문서`의 raw 총계 | `raw/<project>-<feature>-<kind>.md 117개 (위 표 링크)` | **갱신** |
| 날짜 프리픽스 스냅샷 서술 | `**2026-07-28 재스냅샷**: 40 feature · raw 117개. 직전 스냅샷(2026-06-30)은 24 feature · 44개였다.` | **불변** — 특정 시점의 사실 기록이다. 고치면 역사 왜곡 |
| 섹션별 카운트 산문 | `8 feature 전부 spec·arch·result 완비. 뒤 4개가 이번 라운드 신규.` | **불변** — 사람이 쓴 해석 |
| `결정과 근거`·`미해결` 안의 수치 | `24 feature 중 … 10개뿐` 등 | **불변** |

- 갱신 대상 문장은 위 2종으로 **한정 열거**한다. 정규식으로 그 형태를 찾지 못하면 **추측하지 않고 실패 보고**(`catalog_unparsed`, exit 55 — 카탈로그 커밋만 없음. raw는 이미 보존됨).
- **안전성의 근거는 화이트리스트 방식이다(B-3 정정).** 갱신은 위 2종의 명시된 정규식에 매칭되는 줄에**만** 적용된다. 그 외 모든 줄은 대상 자체가 아니므로 불변이 보장된다.
  - 날짜 규칙(`\d{4}-\d{2}-\d{2}`를 포함한 줄은 갱신 대상에서 제외)은 **보조 방어**다 — 화이트리스트 정규식이 우연히 날짜 박힌 스냅샷 서술까지 매칭할 경우를 대비한 2차 차단막이다.
  - 날짜 규칙만으로는 불변 대상을 덮지 못한다는 것이 실측으로 확인됐다: registry L53(`8 feature 전부 spec·arch·result 완비…`)과 L95(`기존 44개 중 38개가 바이트 동일…`)는 **날짜가 없으면서 카운트를 포함**한다. 이 줄들이 안전한 이유는 날짜 규칙이 아니라 **화이트리스트에 없기 때문**이다.
  - **우선순위**: ① 화이트리스트 정규식에 매칭되지 않으면 → 무조건 불변(날짜 유무 무관). ② 매칭되더라도 날짜를 포함하면 → 불변(날짜 규칙이 화이트리스트를 이긴다). 갱신 대상 2종(registry L17·L116)에는 날짜가 없으므로 ②가 정상 동작을 방해하지 않는다.
- kind별 분해 카운트는 §6.3.1의 스냅샷 집합 정의로 계산한다 → F8 게이트(2)와 같은 수를 보게 되어 두 값이 어긋나지 않는다.

### 6.4 F9 — dirty/divergence를 네트워크 없이 판정

F13(네트워크 무호출)과 F9(`git pull --ff-only` 실패 상태 감지)가 문자 그대로는 충돌한다. **조건을 오프라인으로 계산하고 pull은 실행하지 않는다.**

| 검사 | 명령 | 판정 |
|---|---|---|
| dirty | `git status --porcelain` | 비어있지 않으면 중단 + 파일 목록 보고 |
| divergence | `git rev-list --left-right --count @{upstream}...HEAD` (fetch 없음, 마지막으로 알려진 remote ref 사용) | `behind > 0` → 중단(ff-only pull이 필요한 상태 = 우리가 커밋하면 diverge를 만든다). `ahead > 0, behind == 0` → 정상(미push 로컬 커밋). upstream 미설정 → 정상(로컬 전용 저장소, 테스트 fixture 포함) |

`fetch`/`pull`/`push`를 절대 하지 않으므로 코어는 네트워크를 만지지 않는다. "remote가 실제로 앞서 있는지"는 사용자의 마지막 fetch 시점 기준이며, 이 한계를 리포트에 명시한다.

---

## 7. 통합 아키텍처 (렌더링/플러그인 해당 없음)

이 feature에 렌더링 파이프라인은 없다. 통합 표면은 세 개다.

| 표면 | 계약 | 깨지면 |
|---|---|---|
| Claude Code 훅 프로토콜 | Stop: stdin JSON → stdout JSON(`{"continue"}`/`{"decision":"block","reason"}`). PreToolUse: stdin JSON → exit 0/2 + stderr | 파이프라인 정지 또는 전 Bash 명령 차단 → fail-safe 필수 |
| kompound 저장소 규약(AGENTS.md) | raw flat · 마커 형식 · 배치 1건 = log 1줄 · wiki 3파일 외 무수정 | `/lint`·`/ingest`가 drift로 인식. F8 게이트가 1차 방어 |
| SDD 오케스트레이터 | `ORCHESTRATOR_STATE.md`의 `상태` 필드 + Step 4 순서 | T1 미발화(§10.3 파서 이슈 참조) |

---

## 8. 빌드 · 테스트 · 프로파일링 · 운영

- **빌드 없음.** 순수 Python + bash. 패키징은 플러그인 자체(`.claude-plugin/plugin.json`) — 이 feature는 버전 bump 대상이며 `marketplace.json`과 동기화해야 한다(CLAUDE.md).
- **프로파일링**: 게이트는 `gate_perf_warn` 훅으로 100ms 초과를 자체 경고한다. 코어는 `--json` 리포트에 `anchors`·`scanned_files`·`elapsed_ms`를 항상 싣는다(성능 회귀의 관측 지점).
- **진단**: 실패는 전부 verdict 코드 + `errors[]`로 구조화된다. 사람용 텍스트는 항상 "무엇이 왜 막혔는가 + 수동 절차 + 끄는 방법"의 3요소를 포함한다.
- **텔레메트리**: 신규 원격 전송 없음(오프라인 원칙). 누적 신호가 필요하면 기존 `.harness/LEARNING.md` 경로를 쓴다.

## 빌드 프로파일

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

---

## 9. 테스트 전략

### 9.1 레이어별 테스트 타입 (전 레이어 테스트 — SKIP 없음, 타입만 다름)

| 레이어 | 대상 | 테스트 타입 | 프레임워크 | 비고 |
|---|---|---|---|---|
| 순수 함수 | `naming`, `dedup`, `wt_target`, `report`(코드 매핑) | **Unit** | pytest | 입출력이 전부 값. 가장 촘촘히 |
| 설정 해석 | `config` (env/파일/자동탐색/미설정 4단계, 안내 1회) | **Unit** (monkeypatch env + tmp_path) | pytest + monkeypatch | F16 acceptance가 직접 요구 |
| 파일시스템 스캔 | `scan` (앵커·포함/제외·워크트리·깊이 제한) | **Integration** (`fake_workspace`) | pytest + tmp_path | 실제 디렉토리 트리 필요 |
| 멱등 적용 | `apply` **2단 분리** ((i) raw 신규/무동작/갱신 + raw-only 커밋 / (ii) 카탈로그, 단계별 저널·부분 롤백) | **Integration** (`fake_kompound`) | pytest + tmp_path | 2회 실행 무변경 검증. **핵심 케이스: (ii) 실패 시 raw가 롤백되지 않고 커밋되며 워킹트리가 clean(F9 자기 오염 없음)** + 다음 실행이 (i) 무동작·(ii) 재시도로 이어짐 |
| 카탈로그 갱신 | `registry` (표 3형상 · 탐색 3단 · **없는 kind 열 추가** · 카운트 열거) | **Integration** (골든 텍스트 in/out) | pytest | §6.3.2·§6.3.3. 필수 케이스: ① 6열 표에 `ui` 열 추가 시 **기존 행이 `—`로 채워지고 다른 열/줄은 바이트 불변** ② 8열 통합표에 이미 있는 프로젝트가 ②단계로 귀속(신설 안 함) ③ 진짜 새 프로젝트가 ③단계로 7열 신설 ④ 안전 조건 미충족 형상 → `catalog_unparsed` ⑤ 날짜 포함 줄 불변 |
| 카탈로그 갱신 | `wiki_log` (index prepend · log append) | **Integration** (골든 텍스트 + **동시 편집 2항목 보존**) | pytest | F10 acceptance가 "두 항목 유실 없이 모두 남는지"를 요구 → 사람 편집이 선행한 텍스트에 우리 항목을 얹어 양쪽 보존을 확인하는 케이스가 별도로 필요(M-17) |
| 검증 게이트 | `verify` 3종 + 결함 주입 + **`snapshot_set_rule` 경계** | **Integration** | pytest | 게이트별 독립 실패 fixture. 규칙 밖 raw(kind 접미사이지만 프리픽스 미등록)가 카운트에 **포함되지 않음**을 고정 — C-1 회귀 방지의 핵심 |
| git 상태 | `git_state` (dirty/ahead/behind/락/커밋) | **Integration** (`git init` fixture) | pytest + subprocess(git) | 네트워크 없이 upstream 시뮬 |
| CLI 계약 | `cli` 서브커맨드 × 종료 코드 × stdout/stderr 분리 | **Integration** (`main(argv)` 직접 + 서브프로세스 1세트) | pytest | 종료 코드 표가 계약 |
| T2 게이트 스크립트 | `kompound-snapshot-gate.sh` 5분기 + **exit 50/55 경고 통과 vs exit 60 차단** | **Integration** (bash 서브프로세스 + stdin JSON) | pytest + subprocess | 기존 게이트 테스트 관례. A-5의 축 3(카탈로그 실패는 삭제를 막지 않는다)을 고정하는 케이스 필수 |
| 카탈로그 재시도 | (ii) 실패 → 다음 실행에서 카탈로그만 성공 → `log.md` 1줄에 raw/카탈로그 두 시점 표기 | **Integration** (`fake_kompound`, 2회 실행) | pytest | F7 "배치 1건 = 1줄" 유지 검증(§6.3.0) |
| T1 훅 통합 | `stop-pipeline.py` 신규 완료 게이트 (무장·신선도·pending·예산·import 실패 통과·**런타임 상태 write 실패 시 non-block**) | **Unit**(importlib로 `decide` 직접) + **Integration**(`stop-pipeline.sh` 서브프로세스 1세트 — `PYTHONPATH` 없이도 부트스트랩이 성립하는지 확인) | pytest | §9.2. `pipeline.json` 부재(C3) 케이스 필수. 읽기 전용 상태 디렉토리 fixture로 A-1(영구 블록 없음) 고정 |
| T1→T2 승계 | `FAILED`/`GIVEN_UP`(실패 톤) · **`CATALOG_PENDING`(정보 톤)** 이 T2 `gate_warn`으로 노출되고 1회 소비되는지, `DONE`/`PENDING`은 승계되지 않는지 | **Integration** (런타임 상태 fixture + bash 게이트 서브프로세스) | pytest | A-2 채택안의 유일한 사용자 도달 경로. 두 톤이 서로 다른 문구임을 단정(§5.2.3) |
| T1 상태 전이 (D-1) | **(ii)만 실패 → `CATALOG_PENDING` → 다음 Stop에서 재차 block하지 않고 `blocks`도 증가하지 않음**, 이후 카탈로그 성공 시 `DONE`, 새 사이클 무장 시 `PENDING` | **Unit**(importlib `decide` + 런타임 상태 fixture) | pytest | D-1 모순의 회귀 방지. `blocks` 값을 전후 비교해 미증가를 단정 |
| 회귀 안전망 (F17) | `decide`/`DIRECTIVES`/`label_prerequisite_met`/서킷브레이커/`hooks.json` + **부트스트랩 후 9개 Step 불변** | **Characterization(회귀)** | pytest | 수정 **전** GREEN 필수. 부트스트랩 케이스는 수정 후 추가되는 유일한 항목 |
| 정적 규칙 | stdlib-only import · 사용자 절대경로 리터럴 0 · hooks.json 유효성/보존 | **Contract/정적 검사** | pytest (ast/정규식) | F13·F16·F14 acceptance |
| E2E | 실제 kompound + 실제 워크트리 삭제 | **수동 1회 검증 절차(문서화)** | — | §9.4 |

구체 시나리오는 작성하지 않는다 — `sdd-test-automator`의 몫이다.

### 9.2 F17 — 회귀 안전망 구조 (배치·매핑·import 방식)

**파일 배치**

| 파일 | 스코프 |
|---|---|
| `tests/test_stop_pipeline_characterization.py` | F17 스코프 1~4 |
| `tests/test_hooks_json_contract.py` | F17 스코프 5 |

두 파일 모두 상단에 "characterization test — 현재 동작 고정, 스펙 아님. 현재 존재하는 버그까지 함께 고정한다. 의도적 변경 시 이 파일을 함께 갱신한다." 주석과 **스코프 외 항목(`is_stale` staleness · `check_session_match` · `atomic_write`)이 이번 사이클 대상이 아님**을 명시한다(F17 acceptance).

**스코프 → 대상 함수 매핑**

| # | 스코프 | 대상 심볼 (stop-pipeline.py) |
|---|---|---|
| 1 | 라벨 전이 결과 | `decide(stop_data, project_dir, pipeline_path)` — **여기에 "sys.path 부트스트랩 후에도 기존 Step 0~9의 동작이 입력별로 불변"임을 고정하는 케이스를 포함**한다(F17의 6번째 스코프가 아니라 스코프 1의 케이스다. C-4가 도입한 유일한 최상위 변경이 부트스트랩이므로 그 무해성이 스코프 1에서 증명되어야 한다) |
| 2 | DIRECTIVES 선택 로직 | `DIRECTIVES` (L63) + `decide()` Step 8 조회 경로 |
| 3 | 선행조건 판정 | `label_prerequisite_met(label, state, project_dir)` (L296) 및 그것이 참조하는 `has_*` 검사군 |
| 4 | 서킷브레이커 카운팅 | `check_circuit_breaker`(L262) / `increment_breaker`(L279) / `reset_breaker`(L286) |
| 5 | hooks.json 유효성 | 파일 자체 — JSON 파싱 + `PreToolUse:Bash` 기존 5개 커맨드 보존 |

**import 가능성 — 확인 결과와 결정**

`stop-pipeline.py`는 파일명에 하이픈이 있어 `import stop-pipeline`이 문법적으로 불가능하다. 세 방식을 비교했다. (적재 시 모듈 이름 인자는 **유효 식별자 `stop_pipeline`** 을 쓴다 — 선례 `_load()`도 언더스코어 이름을 쓰며, 하이픈 이름은 `sys.modules` 키로는 동작하지만 이후 `import`·`reload`·트레이스백 표시에서 문제를 만든다.)

| 방식 | 판정 | 근거 |
|---|---|---|
| `importlib.util.spec_from_file_location("stop_pipeline", <path>)` | **채택** | (a) 이 레포의 기존 선례다 — `tests/test_self_improve_scripts.py:35-41`의 `_load()`가 하이픈 경로 모듈을 정확히 이 방식으로 적재한다. (b) F17 스코프가 요구하는 것은 **함수·상수 단위** 접근(`DIRECTIVES` 테이블, `increment_breaker`의 상태 변형)이며 이는 in-process import만 제공한다. (c) **부작용 없음을 확인했다** — 모듈 최상위는 상수 정의와 `def`뿐이고 `main()`은 `if __name__ == "__main__"` 가드(L419-420) 안에서만 호출된다. import 시점에 파일 I/O가 없다 |
| 서브프로세스(`stop-pipeline.sh` 실행 + stdin/stdout JSON) | **보조로만** | 최종 계약(stdin→stdout JSON)을 확인하는 스모크 1세트로 유지. 그러나 `DIRECTIVES` 내용·브레이커 내부 상태를 단정할 수 없어 F17 스코프 2·4를 커버하지 못한다 |
| 심링크/사본을 언더스코어 이름으로 만들어 import | 배제 | 테스트가 검증 대상의 사본을 보게 되어 안전망의 의미가 사라진다 |

**안전망 설계 제약(브리틀 방지)** — 스코프 2는 `DIRECTIVES`의 **키 집합 동일성**을 단정하지 말아야 한다. F1이 키 1개(`PHASE4_KOMPOUND_SNAPSHOT_PENDING`)를 추가하기 때문이다. 단정 대상은 ① 기존 16개 라벨 각각의 매핑 존재와 형태 ② `PHASE4_WORKTREE_CREATED == None` ③ 각 directive가 `[SDD-PIPELINE]`로 시작한다는 성질이다. 이렇게 하면 수정 전/후 모두 GREEN이며, 실제 회귀(기존 라벨의 문구·존재 변화)는 잡는다.

또 하나: `decide()`는 `atomic_write`로 pipeline.json을 갱신하므로 안전망 테스트는 반드시 `tmp_path` 위의 상태 파일을 쓰고, `last_updated`를 신선하게 유지해야 한다(`is_stale`이 먼저 걸려 모든 케이스가 `{"continue": True}`로 수렴하는 함정).

### 9.3 공용 fixture

spec F13이 지정한 구조를 `tests/conftest.py`에 **단일 fixture**로 넣는다(중복 정의 금지).

- `fake_kompound_env(tmp_path)` → `{"kompound": Path, "workspace": Path, "config": dict}`
  - `fake_kompound/`: `git init` + 초기 커밋, `raw/`, `wiki/{sdd-spec-registry,index,log}.md`(실제 파일의 형상을 축약 재현 — heterogeneous 표 3형태 + 갱신 대상 카운트 문장 2종 + 날짜 박힌 불변 문장 포함)
  - `fake_kompound/raw/`에는 **§6.3.1 경계 케이스**를 반드시 심는다 — 프리픽스 미등록이면서 kind 접미사로 끝나는 파일(실측 5건의 축약판)이 스냅샷 집합에서 제외되는지 검증하기 위함
  - `fake_workspace/<repo>/docs/sdd/{spec,design/arch,result}`, `<repo>/worktrees/<wt>/docs/sdd/spec` (워크트리 전용 문서 케이스)
  - F16 주입은 `HARNESS_KOMPOUND_CONFIG`(monkeypatch) 또는 `resolve_config()` 오버라이드로
- 기존 `no_network` fixture를 코어 테스트에 적용해 F13 무호출을 물리적으로 보장한다.

**확정(A2)**: 신규 테스트 의존성 없이 pytest + stdlib만으로 진행한다. property-based(hypothesis)는 F4 프리픽스 매핑 검증에 유용하지만 신규 pip 의존이 되어 오프라인 스위트 원칙과 충돌하므로 **도입하지 않는다**. 의존을 늘리지 않는 결정이므로 사용자 승인 대상이 아니다(§10.4-1, 기술 판단).

### 9.4 E2E 검증 경계

자동 테스트의 최외곽은 **"bash 게이트 스크립트 → python CLI → tmp_path의 fake kompound git repo"** 다. 여기까지가 오프라인·결정적으로 재현 가능한 범위다.

경계 밖(자동화하지 않음): 실제 `marvelous_kompound`에 대한 쓰기, 실제 `git worktree remove` 발화, Claude Code 훅 런타임의 실제 stdin/stdout 왕복. 이 3개는 **사람이 1회 수행하는 검증 절차**로 result 문서에 기록한다(F15가 사람 승인을 요구하므로 그 승인 절차에 자연히 포함된다).

---

## 10. 리스크 · 트레이드오프 · 미해결

### 10.1 protected set — 사람 승인 필수

`hooks/lib/self_improve/guard.py`의 `PROTECTED_SET`은 `hooks/enforcement`를 **디렉토리 전체**로 보호한다. 따라서 이 feature가 건드리는 다음 3개는 전부 protected다:

- `hooks/enforcement/stop-pipeline.py` (수정)
- `hooks/enforcement/kompound-snapshot-gate.sh` (신규)
- `hooks/hooks.json` (게이트 등록)

CLAUDE.md: "게이트 스크립트는 자동 생성/수정 금지(사람만)". 이 사이클은 **사용자가 이번 대화에서 명시적으로 지시**해 승인 조건을 충족했다. result 문서와 PR 설명에 "하네스 티어 / 사람 승인 완료" 표기가 있어야 머지 가능하다(F15). 자동 승격 경로(self-improve)로는 이 변경을 만들 수 없다.

### 10.2 트레이드오프 (결정하고 근거를 남긴 것)

| # | 갈림길 | 결정 | 포기한 것 |
|---|---|---|---|
| T-a | T1을 라벨 체인 연장 vs `decide()` 최상단 독립 게이트 | 독립 게이트 | 라벨 상태머신의 개념적 일관성. 그러나 C1(라벨이 오지 않음)·C2(stale/세션)·C3(pipeline.json 부재)로 연장안은 **발화 0회**가 확정적이었다 |
| T-b | 무장 판정: 파일 mtime vs STATE 서명 변화 | 서명 변화(baseline→변화) | 단순함. mtime은 worktree 체크아웃으로 갱신되어 진행 중 사이클에서 오발화한다(LEARNING.md 2026-07-01 file-ownership 오탐과 동일 함정) |
| T-c | F8 실패 시 kompound를 dirty로 남김(spec 문자) vs 전량 롤백 vs **(ii)만 롤백 + raw 커밋** | **(ii)만 롤백 + raw 커밋**(A-5로 조정, §6.3.0) | ① dirty로 남기면 우리가 만든 dirty 때문에 다음 실행이 F9로 막히는 자기 오염이 생긴다. ② 전량 롤백(개정 전 결정)은 "문서가 kompound에 없는 상태"를 스스로 만들어 T2 차단을 사후 정당화하는 순환을 낳는다. ③ 채택안은 문서를 보존하면서 워킹트리를 clean하게 유지한다. 대가: 커밋이 2개로 늘고, 카탈로그가 한 사이클 뒤처진 중간 상태가 정상 상태로 존재하게 된다 |
| T-d | 코어 크래시 시 T2 차단 vs 통과 | 통과(경고). 단 `scan_error`는 차단 | "판정 불가"로 사용자를 갇히게 하지 않는다는 원칙. 대신 삭제 비가역성 때문에 "검증 실패로 판정됨"은 차단한다(§5.2.4) |
| T-e | registry 전면 재생성 vs 외과적 수정 | 외과적 수정 | 구현 단순성. 재생성은 `기존 위키` 열의 사람 지식과 `결정과 근거`·`미해결` 산문을 복원할 수 없고, F7의 "3파일만 갱신·다른 내용 무수정"과 정면 충돌한다 |
| T-f | 스캔: 전체 `os.walk` vs 깊이 제한 앵커 탐색 | 앵커 탐색(기본 깊이 5, 설정 가능) | 이론적 완전성. 전체 walk는 Marvelous급 레포에서 수 초 → PreToolUse 게이트에 부적합. 미탐 위험은 깊이를 리포트에 노출해 가시화 |
| T-g | `state_io` 재사용 vs 자체 구현 | `self_improve.state_io` 재사용 | 패키지 독립성. 원자적 write 구현을 두 벌 유지하는 비용이 더 크다. 역방향 의존은 금지(§4) |
| T-h | 설정 위치: 프로젝트 vs 홈 | 홈(`$CLAUDE_CONFIG_DIR`) 주 + 프로젝트 보조 | 프로젝트 자족성. 머신 전역 값을 repo마다 복제하는 비용·drift가 더 크다(§6.1) |
| T-i | kompound push 포함 vs 로컬 커밋까지 | 로컬 커밋까지 | 자동 배포성. push는 spec 요구가 아니고 네트워크·인증 실패 모드를 새로 만든다 |
| T-j | F8 스냅샷 집합: "kind 접미사" vs "프리픽스 ∩ kind 접미사" | **프리픽스 ∩ kind 접미사**(§6.3.1) | 규칙의 단순함. 그러나 접미사만으로 정의하면 실측 117≠122로 **첫 실행부터 게이트(2)가 항상 실패**하고 T2가 모든 워크트리 삭제를 차단한다. 대가: `prefix_map`을 축소하면 집합 경계가 움직여 카운트가 흔들린다 → 리포트에 프리픽스 목록을 항상 노출해 가시화 |
| T-k | `pending`에 F12 미등록 문서 포함 vs 분리 | **분리**(`pending` ⊥ `unmapped`) | "미박제 총량" 단일 지표의 단순함. 포함하면 T1이 **해소 불가능한 directive로 블록 예산 3회를 태우고** `GIVEN_UP`으로 끝난다. 대가: 지표가 2개로 늘어 리포트·테스트가 둘 다 봐야 한다 |
| T-l | T1 import/부트스트랩 실패: block 1회 vs 통과(경고) | **통과(경고)** | "실패를 시끄럽게"의 최대치. 그러나 §5.2.4의 원칙("판정 불가 → 통과")과 F1("영구 차단 금지")을 동시에 위반하게 된다. 대가: 코어가 깨진 상태에서 T1이 사실상 없는 것과 같아지고 방어가 T2 단독이 된다 → 경고는 stderr로 반드시 출력 |
| T-m | 무장 조건: 서명 변화만 vs 서명 변화 ∧ mtime 상한 | **둘 다**(기본 24h). 단 **mtime은 보조 조건**이다 | 조건 하나로 끝나는 단순함. **근거 정정(A-4)**: mtime 상한은 클론/체크아웃 케이스를 막지 **못한다**(체크아웃이 mtime을 "방금"으로 갱신). 그 케이스의 실제 방어는 `pending == 0` 즉시 통과와 블록 예산 3회다. mtime은 "오래 방치된 STATE에서 서명만 바뀐" 좁은 케이스만 커버한다. 비용이 stat 1회라 유지 가치는 있으나 주 방어로 오해하면 안 된다 |
| T-o | T2 차단 범위: 전 파이프라인 성공 vs **raw 복사 성공만** | **raw 복사 실패만 차단**(A-5 승인, §5.2.4 축 3) | "정합성까지 보장된 상태만 통과"의 엄격함. 그러나 T2의 존재 이유는 "지워도 문서가 남아 있는가"이고 raw 복사가 끝나면 그 목적은 달성된다. 카탈로그 실패로 삭제를 막는 것은 C-1과 같은 구조의 함정(부수 정합성 실패가 기본 작업을 영구히 막음). 대가: 카탈로그가 뒤처진 kompound 상태가 사용자 눈에 안 보인 채 누적될 수 있다 → 경고 메시지에 "무엇이 보존됐고 무엇이 남았는지"를 반드시 포함(§5.2.4) |
| T-p | 무장 조건 강화(상태 전이 추적 도입) vs **현행 유지** | **현행 유지**(사용자 승인 2026-07-29) | 오발화 시나리오(제자리 브랜치 전환으로 STATE 서명이 바뀜)에 대한 이론적 견고함. **사용자 근거**: *"워크트리 기반의 작업을 한다는 전제로 만들어진게 이 sdd라 의미 있는 질문이 아니라고 생각해, 그럴 일도 없을거고"* — SDD는 워크트리 격리를 전제로 설계됐고 하네스가 `worktree-add-gate.sh`로 브랜치 전환을 물리적으로 차단하는 것과도 일관된다. **전제 의존성**: 이 결정은 "워크트리 규율을 따른다"에 의존한다. 워크트리 없이 제자리에서 브랜치를 전환하는 사용 방식이 생기면 오발화가 가능하며(피해는 `pending == 0` 즉시 통과 + 블록 예산 3회로 유계), **그때가 이 결정의 재검토 지점**이다 |
| T-n | 조건 2 미통과 시 baseline: 갱신 vs 보류 | **갱신**(§5.1.3 표 1행) | 미탐 0. **검토 결과(B-9)**: 갱신하면 "STATE가 오래된 동안 서명이 바뀐" 상태가 baseline에 흡수되어, 이후 mtime이 새로워져도 서명이 이미 일치해 무장되지 않는다(미탐 1건). 보류하면 반대로 그 서명이 계속 "변화"로 남아 나중에 무관한 시점에 오발화한다. **갱신을 택한 이유**: 미탐은 T2가 흡수하지만 오발화는 사용자 흐름을 직접 끊는다. 실제 4-2 경로에서는 mtime이 방금이라 조건 2를 항상 통과하므로 이 분기 자체가 정상 경로에 등장하지 않는다 |

### 10.3 이 설계 과정에서 발견한 기존 결함 (범위 밖 — 기록만)

> ⚠️ `hooks/enforcement/lib/state-reader.sh`의 `read_orch_status()`는 `grep -m1 "^status:"`로 `ORCHESTRATOR_STATE.md`를 읽는다. 그러나 실제 파일은 `- 상태: COMPLETED`(한글 라벨, 리스트 항목)를 쓴다(`docs/sdd/ORCHESTRATOR_STATE.md:12`, `skills/sdd-orchestrator/references/state-schema.md:22`). 즉 이 함수는 항상 빈 문자열을 반환하고, 그 결과 `worktree-add-gate.sh`·`branch-gate.sh`의 "Phase 4 활성일 때만 작동" 조건이 **영구히 거짓**이 되어 두 게이트가 사실상 무력화되어 있을 가능성이 있다.
> - 이 feature의 대응: 신규 T1 파서는 `- 상태:`와 `status:` **두 형태를 모두** 허용한다(기존 결함을 계승하지 않는다).
> - 근본 수정(`state-reader.sh` 자체)은 **이 사이클 범위 밖**이며 protected set이라 사람 승인이 필요하다. `.harness/LEARNING.md` 후보로 남긴다.

> 📌 `gate_pass`는 `HARNESS_DEBUG=1`에서만 stderr로 출력된다. F2 acceptance는 "통과 경로도 `gate_pass` 호출을 거친다"까지를 요구하므로 계약은 충족되지만, 평시 관측성은 없다. 그래서 사람이 반드시 알아야 하는 두 통과 경로(F16 미설정 안내·자동박제 성공)는 `gate_warn`을 함께 쓴다.

> 📌 **Stop 훅(T1)의 stderr도 같은 문제를 갖는다(A-2).** `stop-pipeline.sh`가 `exec python3 …`로 stdout JSON만 훅 프로토콜에 넘기고, Stop 훅 stderr는 평시 사용자 화면에 나타나지 않는다. 따라서 T1의 실패는 그 자체로는 비관측이며, 사용자에게 도달하는 경로는 ① **T2 승계 노출**(`FAILED`/`GIVEN_UP` → 다음 `git worktree remove` 시 `gate_warn`) ② `HARNESS_DEBUG=1` 세션의 stderr ③ 런타임 상태 파일 직접 확인 뿐이다. 런타임 상태 write 자체가 실패한 경우 ①이 불가능해 ②③만 남는다 — 이 최악 경로는 결함이 아니라 **알려진 성질**로 규정하고, 그때의 방어는 T2 단독이다.

### 10.4 결정 현황 / 잔여 위험 (승인 대기 0건 — 2026-07-29)

> **사람 승인 대기: 0건 (2026-07-29 기준).** 아래 12개 항목은 전부 승인됨 / 해소됨 / 기술 판단 / 정합 작업 / 후속 작업 / 잔여 위험(수용) 중 하나로 분류됐다. 새 승인 항목이 생기면 이 표 상단의 카운트를 갱신한다.

| # | 항목 | 분류 |
|---|---|---|
| 1 | 테스트 의존성 동결 | **기술 판단(승인 불필요)** |
| 2 | push 미포함 | **승인됨(2026-07-29)** |
| 3 | T1 무장 조건 | **승인됨(2026-07-29)** |
| 4 | registry 표 정책 3개 | **승인됨(2026-07-29, ③ 반전)** |
| 5 | 카운트 갱신 fail-loud | 잔여 위험(수용·모니터링) |
| 6 | spec↔arch 동기화 6항목 | **정합 작업**(N-4로 확장) |
| 7 | kompound `AGENTS.md` 예외 목록 | **후속 작업(범위 밖)** — N-3 |
| 8 | `state_max_age_hours = 24` | **해소됨** |
| 9 | 파일 소유권 오탐 | 잔여 위험(수용·모니터링) |
| 10 | T2 미탐 목록 | **승인됨(2026-07-29)** |
| 11 | 카탈로그 drift 누적 | 잔여 위험(수용·모니터링) |
| 12 | T1 실패 관측성 | 잔여 위험(수용·모니터링) |
| — | T2 차단 범위(T-o) | **승인됨(2026-07-29, A-5)** |
| — | `CATALOG_PENDING` 도입(D-1) | **확정(2026-07-29)** — §5.1.3 |

1. **테스트 의존성 동결 — 기술 판단(승인 불필요)**: pytest + stdlib + `unittest.mock`만. hypothesis 등 신규 pip 의존은 오프라인 스위트 원칙과 충돌하므로 도입하지 않는다(§9.3). 신규 의존을 추가하지 않는 결정은 제약을 늘리지 않으므로 사용자 승인 대상이 아니다.
2. **push 미포함 → 승인됨(2026-07-29)**. 박제 후 kompound는 로컬 커밋(A-5 이후 최대 2개: raw · 카탈로그) 상태로 남고 사용자가 push한다. 코어는 네트워크를 만지지 않는다.
3. **T1 무장 조건 — 현행 유지 → 승인됨(2026-07-29)**. 조건은 "서명 변화 ∧ 상태=COMPLETED ∧ `pending ≥ 1` ∧ `state_max_age_hours` 이내" 그대로이며 **상태 전이 추적은 도입하지 않는다.**
   - **사용자 근거(인용)**: *"워크트리 기반의 작업을 한다는 전제로 만들어진게 이 sdd라 의미 있는 질문이 아니라고 생각해, 그럴 일도 없을거고"* — SDD는 워크트리 격리를 전제로 설계됐으므로, 제자리 브랜치 전환으로 `ORCHESTRATOR_STATE.md` 서명이 바뀌는 오발화 시나리오는 실사용에서 발생하지 않는다. 각 사이클은 자기 워크트리를 갖고 메인 체크아웃은 브랜치를 갈아타지 않는다 — 하네스가 `worktree-add-gate.sh`로 브랜치 전환을 물리적으로 차단하는 것과도 일관된다.
   - **잔여 조건(재검토 지점)**: 이 승인은 **"워크트리 규율을 따른다"는 전제에 의존**한다. 워크트리 없이 제자리에서 브랜치를 전환하는 사용 방식에서는 오발화가 가능하며, 피해는 `pending == 0` 즉시 통과와 블록 예산 3회로 유계다. 전제가 깨지는 사용 방식이 등장하면 이 결정을 재검토한다(T-p).
   - 미탐 성질은 그대로 남는다: 세션의 첫 Stop 훅이 이미 COMPLETED를 관측한 경우 T1은 발화하지 않고 T2가 흡수한다(T-b).
4. **registry 표 정책 → 승인됨(2026-07-29). ③은 방향 반전.** 3가지 표 스키마 공존 — (a) 7열, (b) `기타` 없는 6열, (c) `프로젝트` 열 선행 8열 + `[✓](...)(dev)` 접미사 + `기타` 열의 ` · ` 합성 셀.
   - **① 표 탐색 순서(헤딩 일치 → `프로젝트` 열 → 신설) 승인.** 사용자 결정("분류에 속하지 않으면 새로 만드는 게 맞다")과 충돌하지 않는다 — `moon-harness`는 새 프로젝트가 아니라 8열 통합 표에 이미 3행(L75-77)으로 존재하므로 ②에서 그 표로 귀속되고, **진짜 새 프로젝트만** ③으로 신설된다(§6.3.2 📌).
   - **② 신설 시 표준 형상 7열 승인.**
   - **③ 반전 — "없는 kind 열은 추가하고 기존 행을 `—`로 채운다"**(개정 전: 실패 보고). 근거: 사용자 원칙의 일관된 확장이며, 실패 보고로 두면 그 프로젝트의 카탈로그가 **영구히 갱신 불가**가 된다. `—`는 registry 범례상 사실 그대로의 표기이고 기존 데이터를 훼손하지 않는다. **안전 조건 2개**(kind 6종 이내 · 인지된 3형상 이내)를 만족할 때만 허용하고, 그 밖은 `catalog_unparsed`(경고 후 통과). 상세는 §6.3.2.
   - 리스크 등급: A-5 이후 정책이 틀렸을 때의 결과가 "워크트리 삭제 영구 차단" → "**카탈로그 1사이클 뒤처짐**"으로 내려갔다(raw는 보존·커밋, §6.3.0). 최대 *구현* 리스크이지만 **사용자 흐름을 막는 리스크는 아니다.**
5. **카운트 갱신 fail-loud — 잔여 위험(수용·모니터링)**: §6.3.3은 갱신 2종을 **화이트리스트 정규식**으로 한정하고(날짜 규칙은 보조 방어, B-3) 그 외는 전부 불변으로 둔다. registry에 새로운 형태의 카운트 문장이 생기거나 기존 2종의 형태가 바뀌면 `catalog_unparsed`(exit 55)로 떨어진다. **대가는 A-5로 낮아졌다** — "훅이 멈추고 워크트리에 갇힘" → "카탈로그가 한 사이클 뒤처지고 다음 실행에서 재시도". raw 복사와 삭제 흐름은 영향받지 않는다(등급: 낮음).
6. **spec↔arch 동기화 — 정합 작업 (N-4로 대조 범위 확장)**: 개정 전 이 항목은 `snapshot_set_rule` 하나만 대조 대상으로 삼았고, 그래서 **A-5로 생긴 이탈(T2 차단 사유 집합·커밋 경계)을 잡지 못했다.** Phase 3 진입 전 다음 **6개 항목**을 spec과 대조한다:

   | # | 대조 항목 | arch 정의 위치 |
   |---|---|---|
   | 1 | F8 게이트 (1)(2) 정의 | §6.3.1 |
   | 2 | 게이트 판정 **모집단**(`snapshot_set_rule`) | §6.3.1 |
   | 3 | **T2 차단 사유 집합** (F8 제외 · `write_failed` 포함) | §5.2.4, §6.2 종료 코드 표 |
   | 4 | **커밋 경계** (raw 커밋 / 카탈로그 커밋 2개) | §6.3.0 |
   | 5 | **F7 열 정책** (없는 kind 열 추가 + 안전 조건 2개) | §6.3.2 |
   | 6 | **상태 값 집합** (`CATALOG_PENDING` 포함 6종) | §5.1.2 |

   1·2가 갈리면 게이트(2)가 실측 117 vs 122 실패 상태로 되돌아가고, 3·4가 갈리면 A-5가 무효화되며, 5·6이 갈리면 구현자가 두 문서 사이에서 재결정을 강요받는다(D-1이 정확히 그 상황이었다).
7. **kompound `AGENTS.md` 직접 편집 예외 목록 — 후속 작업(이 feature 범위 밖)**: kompound `AGENTS.md:260`의 예외 목록에는 `index.md` · `log.md` · `my-action-items.md`만 있고 **`sdd-spec-registry.md`는 없다.** 훅을 실제로 켜기 전에 그 목록에 한 줄을 추가해야 `/lint`나 다음 세션의 에이전트가 훅의 registry 쓰기를 SSOT 위반으로 오판하지 않는다.
   - registry 자신의 L1 배너는 이미 "raw 복사 → 그 다음 이 페이지 갱신"을 승인하고 있으므로(§6.3.2 N-3) 두 문서 사이에 불일치가 있는 상태다.
   - **이 작업은 이 feature의 범위 밖**이다 — 훅은 `raw/` · `sdd-spec-registry.md` · `index.md` · `log.md`만 쓰고 `AGENTS.md`는 건드리지 않는다(F7 "3파일만", 단방향 원칙). kompound 쪽에서 `/ingest`로 처리할 **후속 작업**으로 남긴다.
8. **`state_max_age_hours = 24` — 해소됨**. 조건은 "STATE **mtime**이 24h 이내"이고 그 mtime은 Step 4-2가 COMPLETED를 쓴 시각이다. Stop 훅은 매 턴 발화하므로 **4-2를 수행한 턴이 끝나는 즉시** 무장 판정이 이뤄진다 — 사이클 전체가 며칠 걸려도 무관하다. 기본값 24h 유지(설정으로 교체 가능). 남는 성질은 T-m/T-n에 기록.
9. **파일 소유권 오탐 — 잔여 위험(수용·모니터링)**: LEARNING.md 2026-07-01 엔트리대로, 완료된 `ORCHESTRATOR_STATE.md`가 main에 남아 `file-ownership.sh`가 정당한 Edit을 오탐할 수 있다. 이 사이클의 Phase 4에서 부딪힐 수 있으니 오케스트레이터가 인지한다(이 feature의 수정 대상은 아님).
10. **T2 미탐 목록 → 승인됨(2026-07-29)**. `rm -rf $VAR` / 글롭 / `cd <wt> && rm -rf .` 는 잡지 못한다(§5.2.2). 변수 확장·`eval`을 시도하지 않는다는 안전 원칙의 대가로 수용한다.
11. **카탈로그 drift 누적 — 잔여 위험(수용·모니터링)**: (ii) 실패가 반복되면 raw는 쌓이는데 registry/index/log가 뒤처진 상태로 정상 동작하며 누적될 수 있다. **관측의 근거는 `CATALOG_PENDING` 상태**(D-1)다 — 이 상태가 `DONE`으로 덮이면 drift가 완전히 보이지 않게 되므로 별도 값으로 보존한다. 완화책 ① 승계 경고에 "카탈로그 N 사이클 뒤처짐"(정보 톤, §5.2.3) ② 런타임 상태에 `catalog_lag_count` 누적 ③ `check` 리포트에 항상 포함. **자동 에스컬레이션(N사이클 뒤처지면 차단)은 도입하지 않는다** — A-5가 제거한 함정의 재도입이다. ①②③은 구현 세부이므로 엔지니어 재량으로 진행한다.
12. **T1 실패 관측성 — 잔여 위험(수용·모니터링)**: 승계 노출(A-2)을 채택했으나 사용자가 **다음 `git worktree remove`를 실행하기 전까지는** T1 실패를 알 수 없고, 런타임 상태 write 자체가 실패하면 승계도 불가하다(§10.3 두 번째 각주). Stop 반환 JSON에 가시 필드를 동봉하는 대안(A-2의 (b))은 Claude Code Stop 훅 스키마의 표시 동작에 의존해 검증 비용이 크므로 채택하지 않았다.

---

## 11. F1~F17 추적 표

| F | 요구 | 담당 모듈 / 파일 | 비고 |
|---|---|---|---|
| F1 | T1 정상 경로 강제 | `hooks/enforcement/stop-pipeline.py`(완료 게이트 + `DIRECTIVES["PHASE4_KOMPOUND_SNAPSHOT_PENDING"]` + sys.path 부트스트랩), `kompound_snapshot/runtime_state.py`(상태 6종, `CATALOG_PENDING` 포함 — §5.1.3 D-1), `skills/sdd-orchestrator/SKILL.md` Step 4 | §5.1. **spec Acceptance 2번 대응(C-2)**: spec L56의 "`advance_label` 전진 차단"은 실현 불가(`advance_label`은 `pipeline-utils.sh:81`의 bash 함수이고 Phase 4엔 다음 라벨이 없다) → **"Stop 훅이 block을 반환해 전진하지 않음"** 으로 대체 검증된다. 본 설계는 처음부터 Stop 차단으로 구현했으므로 arch 변경은 없다 |
| F2 | T2 안전망 게이트 | `hooks/enforcement/kompound-snapshot-gate.sh` + `kompound_snapshot/{wt_target,cli}.py` (`gate`) | §5.2. **차단 범위 = raw 복사 실패만**(A-5, §5.2.4 축 3). 5개 분기 계약은 유지 |
| F3 | 수집 스코프 | `kompound_snapshot/scan.py` (`KINDS`/`SKIP_DIRS`/`SKIP_NAMES`, 앵커 탐색, `/task` 제외, 워크트리 포함, 부분 실패의 `errors[]` 누적) | **§5.4.1** (비용 상한 근거는 §2.3) |
| F4 | 네이밍 | `kompound_snapshot/naming.py` (`DEFAULT_PREFIX_MAP`, kind 매핑, 날짜/접미사 제거, 프리픽스 접기) + repo 식별 규칙 | **§5.4.2 · §5.4.3** (설정 병합은 §6.1) |
| F5 | dedup | `kompound_snapshot/dedup.py` (`("worktrees" in x, len(x))` 정렬, 내용 상이 시 mtime 최신) | **§5.4.4** |
| F6 | 멱등성 | `kompound_snapshot/apply.py` — (i) 단계. (ii) 실패 후 재실행 시 `unchanged` 무동작으로 재시도가 이어지는 근거 | §6.3, §6.3.0 |
| F7 | registry/index/log 갱신 범위 | `kompound_snapshot/registry.py`(표 탐색 3단 · 행 삽입 · **없는 kind 열 추가**(안전 조건 2개) · 카운트 열거), `kompound_snapshot/wiki_log.py` — **(ii) 단계**. "배치 1건 = log 1줄"은 raw/카탈로그 두 시점 표기로 유지 | §6.3.0, §6.3.2(사용자 승인 2026-07-29), §6.3.3 |
| F8 | 검증 게이트 3종 | `kompound_snapshot/verify.py` — **`snapshot_set_rule` 전제 필수**(+ `apply.py` (ii) 저널 롤백 연동). 게이트 3종은 전부 **카탈로그 정합성** 검사이므로 실패는 (ii) 계열 → T2 경고 통과 | **§6.3.1** (실측 117 vs 122), §6.3.0, §5.2.4 |
| F9 | dirty/diverge 중단 | `kompound_snapshot/git_state.py` | §6.4 |
| F10 | 동시 편집 충돌 양쪽 보존 | `kompound_snapshot/wiki_log.py` (append/prepend-only) + `git_state.py`(dirty 중단) | §6.3, §9.1(2항목 보존 테스트) |
| F11 | 조용한 0건 금지 | `kompound_snapshot/report.py` (verdict/exit code 분리), 전 모듈의 `{"ok"}` 계약, `runtime_state`→T2 승계 노출(A-2) | §6.2, §5.1.3, §10.3 |
| F12 | 미등록 프리픽스 경고만 | `naming.py`(미등록 신호) + `report.py`(`unmapped[]` — `pending`과 배타) + `gate` verdict `unmapped_blocking` | §5.4.3, §5.2.3 |
| F13 | stdlib-only 결정적 코어 | `hooks/lib/kompound_snapshot/` 전체 + `tests/` 정적 검사 | §3, §9.1 |
| F14 | 게이트 패턴 준수 등록 | `hooks/hooks.json`(Bash 배열 마지막), `kompound-snapshot-gate.sh`(`lib/constants.sh`·`lib/logging.sh` 소싱) | §5.2.1 |
| F15 | 2티어 = 하네스 티어, 사람 승인 | 설계 문서 §10.1 + result/PR 표기 | protected set |
| F16 | 환경 설정 주입 | `kompound_snapshot/config.py` (`resolve_config()` 단일 지점 · 키 단위 병합 · `source` 맵), `runtime_state.py`(안내 1회 판정 단독 소유) | §6.1 |
| F17 | 회귀 안전망 선행 | `tests/test_stop_pipeline_characterization.py`, `tests/test_hooks_json_contract.py` | §9.2. Wave 0, F1·F14보다 선행 |
