# cross-project-learning-aggregation 아키텍처 (SDD Phase 2 — SIMPLE)

> 입력: `docs/sdd/spec/2026-06-30-cross-project-learning-aggregation.md` (spec only). UI/API 스펙 없음 (SIMPLE).
> 산출물 성격: 실행 애플리케이션이 아니라 **Claude Code 플러그인 결정적 코어 모듈 1개(신규 I/O 로더) + SKILL.md Phase B 절차 텍스트 수정**. 표준 native arch 템플릿을 이 성격에 맞게 변형함.
> 선행 arch 참조: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md`(결정↔판단 분리, IO 경계 규칙), `docs/sdd/design/arch/2026-06-26-code-mapper.md`(SIMPLE 플러그인 arch 입도).

---

## 1. 아키텍처 요약

이 기능은 **버그 픽스를 위한 I/O 배선**이다. 근본 결함: self-improve의 하네스-티어 승격 게이트 `has_cross_project`는 ≥2 distinct `provenance_repo`를 요구하는데, self-improve가 entries를 **로컬 `.harness/LEARNING.md` 한 파일에서만** 로드하므로(증거: `cursor_runner.run_cursor` — 아래 §5) distinct repo가 구조적으로 항상 1 → 게이트가 영구 False → 하네스 티어 승격 경로가 영원히 봉인된다.

해법은 판정 로직을 건드리지 않는다. `recurrence.py`의 `count_signals`/`has_cross_project`는 **올바르다** — 입력 entries에 2개 repo가 섞여 있으면 알아서 True를 낸다. 결함은 순수하게 **입력 부족**이다. 따라서:

- 신규 결정적 I/O 모듈 `learning_source.py` 하나를 추가해 **로컬 LEARNING.md + 외부 교차-repo store `*.md`**를 읽어 단일 entries 리스트로 합친다.
- 기존 `parse_learning_entry`(파싱)와 `count_signals`(집계)는 무수정으로 재사용한다.
- SKILL.md Phase B 절차의 entries 출처 서술을 "로컬만" → "집계 로더로 합쳐 읽기"로 갱신한다.

아키텍처는 self_improve 패키지의 기존 2레이어 구조를 그대로 따른다 — **순수 코어(I/O 없음) + 얇은 I/O 글루(파일 읽기)**. `learning_source.py`는 글루 레이어에 속한다(파일을 실제로 연다). 판정은 코어가 한다.

```
┌──────────────────────────────────────────────────────────────────────┐
│  진입점 레이어 (프롬프트, LLM 실행)                                     │
│   skills/self-improve/SKILL.md  ← Phase B 절차 (이번에 텍스트만 수정)   │
│   "entries 출처 = 로컬만"  →  "집계 로더로 로컬+store 합쳐 읽기"        │
└───────────────┬──────────────────────────────────────────────────────┘
                │ (LLM이 절차를 따라 글루 함수를 호출)
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  I/O 글루 레이어 (Python stdlib, 파일 읽기 O, fail-safe, 무 raise)      │
│   hooks/lib/self_improve/learning_source.py  ← 신규 (이번 기능의 전부) │
│     load_and_merge(local_learning_path, store_dir) -> list[dict]       │
│       ├─ 로컬 LEARNING.md 읽기 → parse_learning_entry                  │
│       └─ store_dir/*.md 열거 → 파일별 parse_learning_entry → 이어붙임   │
│   (기존 글루) cursor_runner.run_cursor  ← 호출 시퀀스의 현재 진입점     │
└───────────────┬──────────────────────────────────────────────────────┘
                │ (합쳐진 entries 리스트를 그대로 전달)
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  결정적 코어 레이어 (Python stdlib-only, 순수, I/O 0, 무수정 protected) │
│   hooks/lib/self_improve/parser.py    ← parse_learning_entry (무수정)  │
│   hooks/lib/self_improve/recurrence.py← count_signals / has_cross_*    │
│   hooks/lib/self_improve/state_io.py  ← load_state (config 읽기, 무수정)│
└──────────────────────────────────────────────────────────────────────┘
```

데이터 흐름은 단방향이다: **config → store_dir → 로더(로컬+store 병합) → count_signals → has_cross_project**. 영속 상태 쓰기 0(읽기 전용 소비), LEARNING.md 원본 무수정.

---

## 2. 가정 · 제약 · 목표

### 가정 (명시 — 틀리면 교정 요청)
- **A1**: 외부 store(`marvelous_kompound/harness-learning/<repo-id>.md`)는 이미 `parse_learning_entry` 계약(`## marker` H2 + `<!-- tags: ... -->`)을 따른다. 포맷이 다른 파일은 파싱 결과 0건으로 graceful하게 흡수된다(이슈 2 — 형식 오류는 "정상"). (spec 가정 1)
- **A2**: store 경로는 `.harness/config.json`의 `cross_project_store` 키에서만 주입된다. 모듈 내부 경로 하드코딩 0. config/키 부재는 정상 경로(`store_dir=None` → 로컬-only). (R6, F3)
- **A3**: store 생성·sync 책임은 범위 밖. 이 기능은 "store가 있으면 읽는다"는 **소비자**만 구현한다. (spec 미해결 1)
- **A4**: 테스트 프레임워크는 repo 기존 선택(`pytest`, stdlib-only, 오프라인)을 그대로 따른다. 신규 프레임워크 0.
- **A5**: SKILL.md Phase B는 **프롬프트(코드 아님)**다 — entries를 코드 변수로 직접 다루지 않고 글루 스크립트(`cursor_runner.py`, 신규 로더)에 위임하는 절차 서술이다. 따라서 이슈 1의 "호출 지점 변경"은 **글루 스크립트 시퀀스 + 그를 기술하는 절차 문장** 둘 다를 가리킨다(§5 상세).

### 플랫폼 제약
- 산출물 = Python stdlib 모듈 1개 + 마크다운 절차 텍스트. 컴파일 산출물 없음. **fast-scoped** repo(워밍업 빌드 불필요, §빌드 프로파일).
- stdlib only(`json`, `pathlib`, `os`/`os.path`, `typing`). 외부 패키지·네트워크·LLM 호출 0.
- 모든 함수 fail-safe — raise 금지. 예외는 내부 포착 후 빈 리스트/`None` 반환.
- self_improve 패키지의 **결정↔판단 분리** 규칙 준수: I/O는 글루, 판정은 코어. `learning_source.py`는 I/O를 하므로 코어가 아니라 글루 성격이지만, 위치는 패키지 일관성을 위해 `hooks/lib/self_improve/` 아래에 둔다(state_io.py가 이미 같은 패키지에서 I/O를 한다는 선례).

### 목표 (불변량)
- **무수정 불변량 (NFR-1)**: `recurrence.py`, `parser.py`, `state_io.py` 및 기타 기존 `hooks/lib/self_improve/*.py` 전부 git diff 0. 신규 `learning_source.py` + SKILL.md Phase B 텍스트만 변경.
- **하위호환 불변량 (NFR-3)**: `store_dir=None`일 때 결과가 기능 추가 전과 비트단위 동일(로컬-only). 기존 `tests/` 전량 무수정 통과.
- **fail-safe 입도 불변량 (이슈 2)**: 파일 I/O 실패 = catch&skip / 파싱 0건(형식 오류) = 정상 진행. 두 경우 모두 raise 0(§7 상세).
- **격리 불변량**: `count_signals`/`has_cross_project`/`parse_learning_entry` 시그니처·동작·반환 타입 불변. 합쳐진 entries를 그대로 넘긴다.

### protected-set 경계 (Phase 4 오판 차단 — 명문화)
실제 `PROTECTED_SET`은 `hooks/lib/self_improve/guard.py`(L28–38)에 하드코딩된 상수 `{skills/self-improve, skills/pr-converge, agents/harness-improvement-critic.md, hooks/enforcement}`다. 이로부터 이번 기능의 두 변경 대상의 적법성을 못박는다:

- **(a) 신규 `learning_source.py` — protected 무관.** `hooks/lib/self_improve/` 디렉터리 전체는 PROTECTED_SET **밖**이다(보호 대상은 `hooks/enforcement`이지 `hooks/lib`가 아님). 따라서 이 패키지에 신규 모듈을 추가하는 것은 protected 계약과 아무 관련이 없다 — "판정 로직 vs 카탈로그" 같은 논증조차 불필요하다. (단 §10 무수정 불변식은 *기존* 파일에 여전히 적용된다.)
- **(b) `skills/self-improve/SKILL.md` 텍스트 수정 — 적법, NFR-1 위반 아님.** `skills/self-improve`는 PROTECTED_SET **안**이지만, protected 계약의 의미는 "self-improve 루프 *자체의 자동수정* 금지(사람만 수정)"다(`is_protected`는 self-improve의 자동 생성/수정 경로를 차단할 뿐, 사람의 편집을 금지하지 않는다). 이번은 **사람이 주도하는 SDD 사이클**이고 spec(F4·변경 대상 표)이 SKILL.md를 명시적 변경 대상으로 지정했다. 따라서 Phase B 절차 텍스트의 사람 주도 수정은 적법하며, NFR-1(결정적 로직 파일 무수정)과도 무관하다(SKILL.md는 결정적 로직 파일이 아니라 프롬프트 절차다).

> 📌 Phase 4 엔지니어/리뷰어 주의: "SKILL.md를 건드리네 → protected 위반"으로 자동 차단/오판하지 말 것. protected 계약은 *루프의 자기 자동수정*을 막는 것이지 *사람의 SDD 편집*을 막지 않는다. 차단 대상은 오직 (i) 기존 `hooks/lib/self_improve/*.py` 동작 변경(NFR-1), (ii) `learning_source.py`가 결정적 로직 파일을 수정하는 내용 — 둘 다 이번 설계엔 없다.

---

## 3. 모듈 / 디렉터리 경계 (라이브러리 레벨)

> 파일명 단위가 아니라 모듈/책임 경계만 정의한다. 함수 내부 구조는 엔지니어 몫.

| 경계 | 위치 | 책임 | 상태 |
|------|------|------|------|
| 신규 I/O 집계 로더 | `hooks/lib/self_improve/learning_source.py` | 로컬 LEARNING.md + store `*.md` 읽기·병합. 이 기능의 유일한 신규 코드. | **신규** |
| 파서 코어 | `hooks/lib/self_improve/parser.py` | `parse_learning_entry`, `extract_provenance`. 로더가 **호출만** 함. | 무수정 (protected) |
| 재발/교차 판정 코어 | `hooks/lib/self_improve/recurrence.py` | `count_signals`, `has_cross_project`. 합쳐진 entries 소비. | 무수정 (protected) |
| 상태 I/O 코어 | `hooks/lib/self_improve/state_io.py` | `load_state(".harness/config.json")`로 config 읽기. | 무수정 (protected) |
| 패키지 export | `hooks/lib/self_improve/__init__.py` | **무수정** — `load_and_merge`를 export하지 않는다(§아래 보수안 확정). 호출부는 직접 모듈 경로로 import. | 무수정 |
| Phase B 절차 | `skills/self-improve/SKILL.md` | entries 출처 서술 갱신. 결정적 로직 변경 내용 포함 금지. | **텍스트 수정** |
| 코어 테스트 | `tests/` | `learning_source.py`의 pytest(오프라인). 신규 fixture는 store `*.md`. | **신규 테스트** |

### `__init__.py` export 결정 — 보수안 확정 (직접 import, `__init__.py` 무수정)
**결정: `load_and_merge`를 `__init__.py`(import 블록·`__all__`)에 export하지 않는다. `hooks/lib/self_improve/__init__.py`는 1줄도 건드리지 않는다.** 호출부는 직접 모듈 경로로 import한다:

```python
from hooks.lib.self_improve.learning_source import load_and_merge
```

근거: spec NFR-1 Acceptance가 "이번 기능 구현 후 `hooks/lib/self_improve/` 디렉터리의 기존 파일들에 대한 git diff가 없다"를 **문자 그대로** 요구한다. `__init__.py`도 그 디렉터리의 기존 파일이므로, export를 추가하면 형식적으로 diff가 발생해 Acceptance 문구와 충돌한다. 패키지 export 일관성(다른 함수가 `__init__`로 노출됨)이라는 이점은 있으나, 이 기능은 SIMPLE·저위험이고 신규 모듈 직접 import는 표준 Python 관용이라 일관성 손실 비용이 미미하다. 따라서 **NFR-1 무충돌 + 저위험을 우선해 보수안을 채택**한다. (이전 판본의 "승인 게이트 확인 요청"은 본 결정으로 종결.)

### 왜 `cursor_runner.py`에 합치지 않고 신규 모듈인가
`cursor_runner.run_cursor`는 **커서(증분) 의미론**(retro-state.json의 last_processed_marker 이후만 신규)을 담당한다. 교차-repo store 병합은 커서와 직교하는 관심사다(store는 커서 추적 대상이 아님). 둘을 한 함수에 섞으면 `cursor_runner`가 store I/O를 떠안아 단일 책임이 깨지고, `cursor.py`의 무수정도 위태로워진다. 따라서 store 병합은 별도 모듈로 격리하고, 시퀀스 레벨에서 조합한다(§5).

---

## 4. 소유권 · 의존 방향

의존은 **글루 → 코어** 단방향. 코어는 글루를 모른다(역의존 0).

```
SKILL.md Phase B (프롬프트)
   │ 지시
   ▼
learning_source.load_and_merge       (신규 글루, I/O)
   │ 호출 (import)
   ├──────────────► parser.parse_learning_entry   (코어, 무수정)
   │
   ▼ (반환: 합쳐진 list[dict])
recurrence.count_signals             (코어, 무수정)
   │
   ▼
recurrence.has_cross_project         (코어, 무수정)

state_io.load_state(".harness/config.json")  (코어, 무수정)
   │ 반환 dict["cross_project_store"]
   ▼
  store_dir 인자  ──► learning_source.load_and_merge
```

- `learning_source.py`는 `parser`(같은 패키지 코어)에만 의존한다. `recurrence`/`state_io`는 import하지 않는다 — config 읽기와 count_signals 호출은 **호출자(글루 시퀀스/SKILL 절차)**가 조립한다. 이로써 로더는 "경로 2개 → entries 1개"라는 순수 변환 책임만 갖고, config 스키마 지식을 떠안지 않는다(경로 주입 원칙 R6/NFR-2 준수).
- 코어 3종(parser/recurrence/state_io)은 신규 모듈을 전혀 참조하지 않으므로 git diff 0이 자연 보장된다(NFR-1).

---

## 5. 공개 함수 시그니처 · 호출 시퀀스 (이슈 1 해소 — 진입점 특정)

### 5.1 신규 공개 API

```python
# hooks/lib/self_improve/learning_source.py

def load_and_merge(
    local_learning_path: str | os.PathLike | None,
    store_dir: str | os.PathLike | None,
) -> list[dict]:
    """로컬 LEARNING.md + 교차-repo store *.md 를 합쳐 단일 entries 리스트 반환.

    순서: 로컬 entries 먼저, 그 뒤에 store entries(파일명 정렬 순) 이어붙임.
    어떤 경우에도 raise 하지 않는다 (fail-safe). 실패한 소스는 빈 기여.
    """
```

보조(내부) 함수는 엔지니어 재량이나, 책임 경계상 다음 2개를 권장(파일명 아님 — 함수 책임 가이드):
- 로컬 1파일 읽기·파싱 (없거나 읽기 실패 → `[]`)
- store 디렉터리 열거·파일별 읽기·파싱·병합 (디렉터리 아님/열거 실패 → `[]`, 개별 파일 실패 → 해당 파일만 skip)

### 5.2 현재 진입점 추적 (코드 증거)

self-improve가 entries를 **어디서 로드하는가** — 코드 레벨 진입점은 `skills/self-improve/scripts/cursor_runner.py`의 `run_cursor(harness_dir)`다:

- `run_cursor`는 `<harness_dir>/LEARNING.md`를 `read_text`로 읽고(증거: cursor_runner.py L70–79), `get_new_entries(learning_text, last_marker)`로 **로컬 한 파일만** 파싱·커서필터한 entries를 반환한다.
- SKILL.md Phase A "1. `.harness/LEARNING.md`를 읽는다"가 이 글루의 절차 서술 대응이다.
- Phase B(SKILL.md L77–85 "진단·클러스터")는 그 entries로 클러스터링하며, F16 섹션(L150–175)의 `> 📌 Phase B 클러스터링 시 count_signals()를 호출` 문장이 **count_signals 호출 지점의 절차 서술**이다.

즉 현재 시퀀스: `run_cursor` → (로컬 entries) → 클러스터링 → `count_signals(로컬 entries)` → `has_cross_project` = 구조적으로 단일 repo → 영구 False. **이것이 결함의 정확한 위치다.**

### 5.3 신규 시퀀스 (정확히 어디서 무엇을 바꾸는가)

코드 시퀀스(글루 레벨)와 절차 시퀀스(SKILL 텍스트)를 분리해 명시한다.

**(a) 코드/글루 시퀀스** — Phase B 진입 직전, count_signals 호출 직전에 store 병합을 삽입:

```
1. cfg = state_io.load_state(".harness/config.json")          # None 가능 (파일 없음/파싱 실패)
2. store_dir = (cfg or {}).get("cross_project_store") or None  # 키 없음/null/"" → None
3. merged = learning_source.load_and_merge(
       local_learning_path = <harness_dir>/LEARNING.md,
       store_dir           = store_dir,
   )                                                           # 로컬+store 합친 entries
4. counter = recurrence.count_signals(merged)                  # ← 기존 count_signals, 합쳐진 입력
5. recurrence.has_cross_project(counter, cluster_key)          # 이제 True 가능
```

> 📌 **커서와의 관계**: `run_cursor`의 커서(증분) 의미론은 **로컬 LEARNING.md에만** 적용된다(신규 엔트리 추적은 로컬 repo 사이클 산물이므로). 교차-repo store는 "현재 교차 증거 스냅샷"이라 커서 필터 대상이 아니다 — store entries는 매 회고에서 전량 재로드해 `count_signals`에 합산한다. 따라서 신규 시퀀스는 `run_cursor`(로컬 신규 entries) 결과와 `load_and_merge`(로컬 전체 + store)를 **둘 다 활용**하되, **`has_cross_project` 판정용 입력은 `load_and_merge`의 merged**를 쓴다. 클러스터링 대상 *신규* 엔트리 식별은 여전히 `run_cursor`가 담당(중복 처리 방지). 이 분리는 엔지니어가 시퀀스로 조립하며 `cursor.py`/`cursor_runner.py`는 무수정으로 둔다(store 병합을 cursor_runner에 넣지 않는 §3 결정의 귀결).

**(b) SKILL.md 절차 텍스트 변경 지점** (정확한 위치):
- **Phase A 문장 1 (L73)** 또는 **Phase B 도입부**: "entries 출처"를 기술하는 곳에 "집계 로더(`learning_source.py`)로 로컬 LEARNING.md + (config의 `cross_project_store`가 가리키는) 교차-repo store `*.md`를 합쳐 읽는다. config/키 없으면 로컬-only로 기존과 동일" 추가. (F4)
- **F16 섹션 `> 📌` 문장 (L175)**: "Phase B 클러스터링 시 `count_signals()`를 호출" → "Phase B에서 **집계 로더로 합쳐진 entries**를 `count_signals()`에 전달하여 교차 프로젝트 여부를 확인한다. store 미설정 시 로컬 entries만 반영(하위호환)." 로 정밀화.
- **변경 금지**: Phase C/D 절차, F17/F18/F19, 안전 규칙, 결정적 로직 파일 언급(recurrence.py 등 "무수정" 서술은 유지). (F4 Acceptance)

---

## 6. config / 데이터 흐름 (이슈 1 보강 — config→store→로더)

```
.harness/config.json
   │  { "cross_project_store": "/abs/path/to/marvelous_kompound/harness-learning" }
   │
   ▼  state_io.load_state(".harness/config.json")
  dict | None
   │   ├─ None            (파일 없음 / JSON 파싱 실패 / 최상위가 dict 아님)  ─┐
   │   ├─ 키 없음                                                          ─┤→ store_dir = None
   │   └─ 값이 null/""                                                     ─┘   (로컬-only)
   │   └─ 유효 경로 문자열  ────────────────────────────────► store_dir = "<path>"
   ▼
learning_source.load_and_merge(local=<harness>/LEARNING.md, store_dir=store_dir)
   │   ├─ 로컬 읽기 OK     → parse_learning_entry → [e1, e2, ...]
   │   ├─ 로컬 읽기 실패    → [] (catch&skip)
   │   ├─ store_dir=None   → store 기여 없음
   │   ├─ store_dir 유효   → glob *.md (정렬) → 파일별 parse → 이어붙임
   │   │      ├─ 파일 읽기 실패 → 그 파일 skip
   │   │      └─ 파싱 0건(H2 없음) → 그 파일 0 기여 (정상)
   │   └─ store_dir 부재/디렉터리 아님/열거 실패 → store 기여 없음 (catch&skip)
   ▼
list[dict]  (로컬 + store 병합, provenance_repo 태그 보존)
   ▼
count_signals → cross_repo_set 에 distinct repo 누적 → has_cross_project
```

- `learning_source.py`는 `state_io`를 import하지 않는다 — config 읽기는 호출자가 하고 `store_dir`만 주입(§4 의존 방향). 경로 해석 기준 디렉터리도 모듈 내부에 두지 않는다(받은 경로를 `pathlib.Path` 그대로). (R6, NFR-2, spec 가정 2)
- store는 **읽기 전용**. 어떤 코드 경로도 store나 config를 쓰지 않는다.

---

## 7. fail-safe 에러 계약 (이슈 2 해소 — 입도 명시)

`learning_source.py`의 모든 함수는 **raise 0**. 두 실패 부류를 **명확히 구분**한다:

| 부류 | 트리거 | 처리 | 결과 entries | raise? |
|------|--------|------|-------------|--------|
| **(A) 파일/디렉터리 I/O 실패** | 로컬 파일 없음·권한·인코딩·IO 오류; store_dir 부재·디렉터리 아님·열거 오류; 개별 store 파일 읽기 실패 | `try/except Exception` 으로 **catch & skip** | 해당 소스는 **빈 기여**(로컬 실패→로컬 []; store 디렉터리 실패→store []; 개별 파일 실패→그 파일만 skip, 나머지 계속) | No |
| **(B) 파싱 0건 (형식 오류 마크다운)** | `parse_learning_entry`가 H2 헤더 없는/빈 텍스트에 대해 `[]` 반환 | **정상**으로 취급, 다음 파일 계속 | 그 파일 0건 기여 — 에러 아님 | No (애초에 parser가 raise 안 함) |

핵심 구분(이슈 2):
- **(A)는 예외 포착**이다. `Path.read_text`/`Path.iterdir`/`glob`이 던질 수 있는 `OSError`·`UnicodeDecodeError`·`PermissionError` 등을 `except Exception`으로 잡아 그 소스만 비우고 계속한다. 절대 전파하지 않는다.
- **(B)는 예외가 아니다**. parser는 fail-safe라 형식 오류 입력에 `[]`를 반환할 뿐 raise하지 않는다(증거: parser.py L63–64, L75–76). 로더는 `[]`를 정상 결과로 받아 그대로 병합(0건 추가)하면 된다 — try/except 불필요. "불량 *.md 섞여도 건너뛰고 나머지 처리"(F2 Acceptance)는 이 (B) 경로로 자연 충족된다.

> 📌 **부분 실패 ≠ 전체 차단**: store 디렉터리에 10개 파일 중 3개가 (A) 또는 (B)여도 나머지 7개는 집계된다. 로컬 (A) 실패여도 store만으로 진행한다. 어떤 단일 소스도 전체를 무너뜨리지 않는다(F2 "부분 실패가 전체를 차단하지 않는다").

> 📌 **모듈 import 부작용 0** (NFR-2 Acceptance): 모듈 최상위에서 파일 읽기·환경변수 접근·경로 계산 금지. 모든 I/O는 `load_and_merge` 호출 시점에만.

---

## 8. 빌드 · 테스트 · 운영 관심사

- **빌드**: 컴파일 없음. fast-scoped(아래 빌드 프로파일). 진입 워밍업 빌드 불필요.
- **import 경로**: `from hooks.lib.self_improve.learning_source import load_and_merge`. `tests/conftest.py`가 repo 루트를 `sys.path`에 넣으므로 어느 cwd에서도 동작.
- **오프라인 보장**: stdlib-only이므로 `tests/`가 네트워크 미접촉. `no_network` 픽스처로 명시 가드 가능(conftest 제공).
- **프로파일링/텔레메트리**: 비목표(SIMPLE, 작은 I/O). spec 미해결 2(store 파일 수 증가 성능)는 Phase 2 검토 — 현 단계 측정 안 함.
- **롤백**: 단일 신규 모듈 + SKILL 텍스트 diff. 되돌리기 = 모듈 삭제 + `__init__.py` export 1줄 제거 + SKILL 문장 원복.

---

## 9. 테스트 전략

> 레이어 = 순수/글루 함수 1개(`learning_source.py`). 모든 레이어를 테스트한다 — 타입만 다르다. FULL/SKIP 없음. 구체 시나리오는 test-automator가 도출하며, 여기서는 **타입 · 프레임워크 · 검증 경계**만 정의한다.

| 레이어 | 대상 | 테스트 타입 | 프레임워크 | RED 먼저 |
|--------|------|------------|-----------|---------|
| I/O 글루 단위 | `load_and_merge` (로컬+store 병합, fail-safe 분기) | **단위** | `pytest` (repo 기존) | 예 |
| 통합 (코어 합류) | `load_and_merge` → `count_signals` → `has_cross_project` 결선 | **통합** | `pytest` | 예 |
| 회귀 (하위호환) | `store_dir=None` → 기존 로컬-only 결과 동일 | **단위/통합** | `pytest` | 예 |
| 무수정 불변식 | `hooks/lib/self_improve/` 기존 파일 git diff 0 | **검증(가드)** | git diff 확인 (CI/리뷰) | n/a |

### E2E 검증 경계
이 기능은 LLM 절차(SKILL Phase B)가 글루를 호출하는 배선이다. **E2E(라이브 claude -p) 경계는 `evals/`** — config가 가리키는 store가 있을 때 self-improve가 하네스 티어 제안 경로를 *열 수 있는지*를 라이브로 확인. 단 오프라인 결정적 검증(`tests/`)이 핵심 계약(병합·fail-safe·has_cross_project=True)을 전량 커버하므로, E2E는 절차 배선 sanity에 한정(범위는 test-automator/이후 단계).

### Fixture 전략 (NFR-4)
- 실제 harness-learning 포맷(`## marker` H2 + `<!-- tags: domain=, stage=, provenance_repo= -->`)을 쓴다. 기존 `tests/fixtures/sample_learning.md` 포맷과 `tests/conftest.py`의 `sample_entries`(provenance_repo 포함) 패턴을 참조.
- 신규 fixture: 임시 store 디렉터리에 `*.md` 2건 이상(`tmp_path` 활용). 최소 1건은 로컬과 **동일 domain·다른 provenance_repo**.

### 경계 시나리오 (test-automator가 구체화할 경계만 명시)
- **2-repo 교차 회귀 (NFR-4 핵심)**: 로컬 `domain=test-adequacy, provenance_repo=moon-harness` 1건 + store `domain=test-adequacy, provenance_repo=Marvelous` 1건 → `load_and_merge` → `count_signals` → `has_cross_project(counter, "test-adequacy") == True`. (spec 검증 시나리오 "정상 집계")
- **로컬-only 보존**: `store_dir=None` → 단일 repo → `has_cross_project == False`. (하위호환)
- **store 경로 없음/잘못됨**: 존재하지 않는 경로 → raise 0, 로컬-only.
- **불량 store 파일**: H2 없는 `*.md` 포함 → 그 파일 0 기여, 나머지 정상((B) 경로).
- **개별 파일 I/O 실패**: 권한/인코딩 오류 파일 1건 → 그 파일만 skip, 나머지 집계((A) 경로).
- **config 부재/키 부재/null/""**: 전부 `store_dir=None`로 귀결 → 로컬-only.

---

## 빌드 프로파일

> 출처: `CLAUDE.md`(빌드/테스트 섹션) + 본 세션 파일시스템 확인 2026-06-30

| 필드 | 값 | 비고 |
|------|-----|------|
| 유형 | fast-scoped | pytest 직접 실행. 빌드 산출물 없음(순수 Python). 워밍업 빌드 불필요 |
| 워밍업 빌드 | (없음) | fast-scoped — Phase 4 진입 워밍업 생략 |
| 증분 빌드 | (없음) | 컴파일 단계 없음 |
| 테스트 실행 | `<PY> -m pytest tests/test_learning_source.py -q` | `<PY>`=아래 인터프리터 주의 참조. 전량: `<PY> -m pytest tests/ -q` |
| 테스트 필터 문법 | `<PY> -m pytest tests/test_learning_source.py::TestClass::test_method` | 노드 ID로 태스크 스코프 지정 |
| clean 정책 | no-clean | `__pycache__` 보존 — 태스크 간 clean 불필요 |

> 📌 **인터프리터 주의 (Phase 4 진입 시 1회 확인 권장)**: 이 머신은 homebrew가 `/usr/local`에 있어 **`python3 -m pytest tests/ -q`(= `/usr/local/bin/python3.14`, pytest 9.0.3)로 동작 확인됨**. `CLAUDE.md`가 문서화한 `PATH="/opt/homebrew/bin:$PATH" ...`는 **이 머신 기준 경로가 상이**하다(`/opt/homebrew`가 아닌 `/usr/local` Cellar). `tests/__pycache__/test_recurrence.cpython-314-pytest-9.0.3.pyc`도 마지막 실행이 **CPython 3.14 + pytest 9.0.3**임을 뒷받침한다. 엔지니어는 환경이 다를 수 있으니 Phase 4 진입 시 `python3 -m pytest --version`(또는 `which -a python3 python3.14`)으로 **pytest 가능한 실제 인터프리터(`<PY>`)를 확정**해 위 표의 `<PY>`를 치환하라(pyenv/uv/venv 가능성). 명령 자체는 `<PY> -m pytest tests/...`로 고정.

---

## 10. 리스크 · 트레이드오프 · 마이그레이션

| 리스크 | 영향 | 완화 |
|--------|------|------|
| `__init__.py` export 추가가 NFR-1 "기존 파일 무수정"과 형식적 충돌로 비칠 수 있음 | 리뷰 마찰 | §3 근거(카탈로그 vs 판정 로직)로 정당화. 보수 옵션(직접 모듈 import) 병기. **승인 게이트 확인 항목**. |
| 커서(증분)와 store(전량) 의미론 혼동으로 store entries가 커서 필터에 걸려 누락 | has_cross_project 다시 False | §5.3 `> 📌`로 분리 명시 — store는 매 회고 전량 로드, 커서는 로컬에만. 통합 테스트로 가드. |
| SKILL.md가 프롬프트라 "호출 지점"이 코드처럼 한 줄로 특정 안 됨 | 이슈 1 재발 | §5에서 코드 시퀀스(글루)와 절차 문장(SKILL 위치 L73/L175)을 **둘 다** 특정해 해소. |
| store 파일 수 급증 시 매 회고 전량 재읽기 비용 | 성능 | spec 미해결 2 — Phase 2에서 파일 수 상한/lazy 검토. 현 단계 비목표. |
| 인터프리터 경로 불일치로 RED/GREEN 실행 실패 | TDD 무결성 | 빌드 프로파일 `> 📌`로 Phase 4 진입 시 `<PY>` 확정 강제. |

### 마이그레이션
신규 코드 추가형이라 마이그레이션 사실상 없음. 기존 self-improve 동작은 `store_dir=None` 경로로 **비트단위 보존**(NFR-3). config에 `cross_project_store`를 채우는 순간만 신규 경로가 활성화되는 opt-in. 롤백은 §8 참조.

---

## 부록 A — 블로커 2건 해소 매핑

| 블로커 | 해소 위치 |
|--------|----------|
| **이슈 1 — 구현 진입점 특정** | §5.2(현재 진입점 = `cursor_runner.run_cursor`, 코드 증거 L70–83), §5.3(신규 코드 시퀀스 5단계 + SKILL 절차 변경 지점 L73·L175 특정), §6(config→store→로더 흐름) |
| **이슈 2 — fail-safe 에러 계약 입도** | §7(부류 A=I/O 실패 catch&skip / 부류 B=파싱 0건 정상진행, 표 + 부분실패 규칙, import 부작용 0, 양쪽 raise 0) |
